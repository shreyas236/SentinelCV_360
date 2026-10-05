"""Cryptographic OIDC contract tests, independent of a running identity server."""
import base64,json,time,unittest
from cryptography.hazmat.primitives.asymmetric import rsa,padding
from cryptography.hazmat.primitives import hashes
from local.oidc import verify_token,identity
def b64(value):return base64.urlsafe_b64encode(value).decode().rstrip('=')
class OIDCTest(unittest.TestCase):
    def test_signature_issuer_audience_nonce_expiry_and_fixed_roles(self):
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048);numbers=key.public_key().public_numbers()
        jwks={'keys':[{'kid':'local-idp','kty':'RSA','n':b64(numbers.n.to_bytes(256,'big')),'e':b64(numbers.e.to_bytes(3,'big'))}]}
        claims={'iss':'https://idp.local/realms/sentinel','aud':'sentinel-api','azp':'sentinel-api','sub':'user-123','exp':time.time()+300,'nonce':'state-nonce','realm_access':{'roles':['sentinel-user']}}
        def token(payload):
            raw=b64(json.dumps({'kid':'local-idp','alg':'RS256'}).encode())+'.'+b64(json.dumps(payload).encode());return raw+'.'+b64(key.sign(raw.encode(),padding.PKCS1v15(),hashes.SHA256()))
        valid=verify_token(token(claims),jwks,claims['iss'],'sentinel-api','state-nonce');self.assertEqual(identity(valid)['role'],'analyst')
        for change in ({'iss':'https://evil.local'},{'aud':'other-client'},{'exp':time.time()-1},{'nonce':'wrong'}):
            with self.assertRaises(ValueError):verify_token(token({**claims,**change}),jwks,claims['iss'],'sentinel-api','state-nonce')
        tampered=token(claims).split('.');tampered[1]=b64(json.dumps({**claims,'sub':'admin'}).encode())
        with self.assertRaises(Exception):verify_token('.'.join(tampered),jwks,claims['iss'],'sentinel-api')
        with self.assertRaises(ValueError):identity({**claims,'realm_access':{'roles':['sentinel-user','sentinel-admin']}})
if __name__=='__main__':unittest.main()
