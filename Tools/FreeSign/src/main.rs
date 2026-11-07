use std::{env, fs, future, path::PathBuf};

use isideload::{
    anisette::remote_v3::RemoteV3AnisetteProvider,
    auth::apple_account::{AppleAccount, TwoFactorCallbackParams, TwoFactorCallbackResponse},
    dev::{developer_session::DeveloperSession, devices::DevicesApi, teams::TeamsApi},
    sideload::{SideloaderBuilder, TeamSelection, builder::MaxCertsBehavior},
    util::{
        callbacks::{ExtensionsBehaviorCallbackBox, MaxCertsCallbackBox},
        fs_storage::FsStorage,
    },
};
use rootcause::prelude::*;

fn required(name: &str) -> String {
    env::var(name).unwrap_or_else(|_| panic!("Missing required environment variable {name}"))
}

async fn run() -> Result<(), Report> {
    let email = required("APPLE_ID").trim().to_ascii_lowercase();
    let password = required("APPLE_PASSWORD");
    let udid = required("IPHONE_UDID");
    let state = PathBuf::from(required("SIGNING_STATE_DIR"));
    let input = PathBuf::from(required("INPUT_IPA"));
    let output = PathBuf::from(required("SIGNED_APP_PATH_FILE"));
    let helper = required("SIGNING_HELPER");
    fs::create_dir_all(&state)?;
    let anisette = RemoteV3AnisetteProvider::new(
        &env::var("ANISETTE_URL").unwrap_or_else(|_| "https://ani.iloader.app".into()),
        Box::new(FsStorage::new(state.join("anisette"))),
        "0".into(),
    )?;
    let mut account = AppleAccount::builder(&email)
        .anisette_provider(anisette)
        .build()
        .await?;
    let session_path = state.join("session.plist");
    let mut session = None;
    if session_path.exists() {
        account.spd = Some(plist::from_file(&session_path)?);
        session = DeveloperSession::from_account(&mut account).await.ok();
    }
    if session.is_none() {
        println!("Authenticating with Apple. A verification code may be requested.");
        account.login(&password, move |challenge: TwoFactorCallbackParams| {
            let helper = helper.clone();
            async move {
                if challenge.unknown {
                    println!("::notice::Apple requested another verification method. Requesting a code on trusted devices.");
                    return Ok(TwoFactorCallbackResponse::SendToDevices);
                }
                if challenge.last_error.is_some() {
                    println!("::warning::Apple did not accept the previous verification code. Requesting a fresh code; update APPLE_2FA_CODE and send it again.");
                    return Ok(TwoFactorCallbackResponse::ResendCode);
                }
                println!("::notice::Waiting for 2FA. Set APPLE_2FA_CODE to the latest code, then run the Send verification code action.");
                let response = tokio::process::Command::new("python3")
                    .arg(helper).arg("wait-code").output().await?;
                if !response.status.success() {
                    bail!("Verification code timed out or could not be retrieved");
                }
                let code = String::from_utf8(response.stdout)?.trim().to_string();
                if code.len() != 6 || !code.bytes().all(|b| b.is_ascii_digit()) {
                    bail!("Invalid verification code response");
                }
                println!("::notice::Received the encrypted verification code. Submitting it to Apple.");
                Ok(TwoFactorCallbackResponse::SubmitCode(code))
            }
        }).await?;
        session = Some(DeveloperSession::from_account(&mut account).await?);
        if let Some(spd) = &account.spd {
            plist::to_file_xml(&session_path, spd)?;
        }
    }
    let mut session = session.unwrap();
    let teams = session.list_teams().await?;
    let team_id = env::var("APPLE_TEAM_ID").unwrap_or_default();
    let team = if !team_id.is_empty() {
        teams
            .into_iter()
            .find(|t| t.team_id == team_id)
            .ok_or_else(|| report!("APPLE_TEAM_ID does not match an available team"))?
    } else if teams.len() == 1 {
        teams.into_iter().next().unwrap()
    } else {
        bail!("Multiple Apple teams available. Set APPLE_TEAM_ID to select one.");
    };
    println!("Registering the target device and obtaining signing materials.");
    session
        .ensure_device_registered(&team, "Asspp iPhone", &udid, None)
        .await?;
    let mut signer = SideloaderBuilder::<MaxCertsCallbackBox, ExtensionsBehaviorCallbackBox>::new(
        session, email,
    )
    .storage(Box::new(FsStorage::new(state.join("certificate"))))
    .machine_name("Asspp GitHub Actions".into())
    .team_selection(TeamSelection::First)
    .max_certs_behavior(MaxCertsBehavior::Error)
    .build();
    println!("Signing the IPA.");
    let (app, _) = signer
        .sign_app(
            input,
            Some(team),
            false,
            None::<fn(f32) -> future::Ready<()>>,
            None,
            None,
        )
        .await?;
    fs::write(output, app.to_string_lossy().as_bytes())?;
    println!("Signing completed. Packaging and validation follow.");
    Ok(())
}

#[tokio::main]
async fn main() {
    let _ = rustls::crypto::ring::default_provider().install_default();
    if isideload::init().is_err() {
        eprintln!("::error::Unable to initialize the signing library.");
        std::process::exit(1);
    }
    if let Err(error) = run().await {
        // Avoid debug formatting, which may include sensitive protocol attachments.
        let message = error.to_string();
        let sensitive = [
            "APPLE_ID",
            "APPLE_PASSWORD",
            "IPHONE_UDID",
            "SIGNING_STATE_PASSWORD",
        ];
        let redacted = sensitive
            .iter()
            .fold(message, |text, name| match env::var(name) {
                Ok(value) if !value.is_empty() => text.replace(&value, "[redacted]"),
                _ => text,
            });
        eprintln!(
            "::error::Signing failed: {}",
            redacted.replace(['\n', '\r'], " ")
        );
        std::process::exit(1);
    }
}
