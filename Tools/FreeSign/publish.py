"""Publish the verified IPA using a short-lived GitHub Actions OIDC identity."""
import json, os, plistlib, subprocess, urllib.parse, urllib.request, zipfile
from pathlib import Path
ORIGIN = 'https://shengsheng-install.amwss2006.chatgpt.site'

def metadata(path):
    with zipfile.ZipFile(path) as archive:
        roots = [n[:-len('Info.plist')] for n in archive.namelist()
                 if n.startswith('Payload/') and n.count('/') == 2 and n.endswith('/Info.plist')]
        if len(roots) != 1:
            raise ValueError('Expected one main application')
        root = roots[0]
        info = plistlib.loads(archive.read(root + 'Info.plist'))
        profile = plistlib.loads(subprocess.run(
            ['security', 'cms', '-D'], input=archive.read(root + 'embedded.mobileprovision'),
            capture_output=True, check=True).stdout)
        return dict(bundleId=info['CFBundleIdentifier'], build=info['CFBundleVersion'],
                    version=info['CFBundleShortVersionString'], minimumOS=info['MinimumOSVersion'],
                    expires=profile['ExpirationDate'].isoformat() + 'Z')

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def main():
    path = Path(os.environ['SIGNED_IPA'])
    m = metadata(path)
    token_url = os.environ['ACTIONS_ID_TOKEN_REQUEST_URL']
    parsed = urllib.parse.urlparse(token_url)
    if parsed.scheme != 'https' or not parsed.hostname.endswith('.actions.githubusercontent.com'):
        raise SystemExit('Unexpected OIDC token endpoint')
    url = token_url + ('&' if '?' in token_url else '?') + urllib.parse.urlencode({'audience': ORIGIN})
    opener = urllib.request.build_opener(NoRedirect())
    req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + os.environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN']})
    with opener.open(req, timeout=30) as response:
        token = json.load(response)['value']
    req = urllib.request.Request(ORIGIN + '/api/publish', data=path.read_bytes(), method='POST', headers={
        'Authorization': 'Bearer ' + token, 'Content-Type': 'application/octet-stream',
        'X-Ipa-Metadata': json.dumps(m, separators=(',', ':'))})
    try:
        with opener.open(req, timeout=120) as response:
            result = json.load(response)
    except Exception as error:
        raise SystemExit('Website publication failed; signed IPA remains in Actions artifacts.') from None
    if result.get('url') != ORIGIN:
        raise SystemExit('Unexpected publication response')
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
        summary.write('\n### Safari installation\n[Open Asspp installation page](' + ORIGIN + ')\n')
    print('Signed IPA published to ' + ORIGIN)

if __name__ == '__main__':
    main()
