"""Encrypt the approved Modal credential to a VM-only temporary RSA key."""
import base64
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes
from setup_kimi_200 import invoke

ROOT=Path(__file__).resolve().parents[1]
secret=ROOT/'runs/azure-control/.kimi-modal-token'
public=invoke(r'''
$d='C:\iterate-hackathon\secrets\kimi-200'
New-Item -ItemType Directory -Force -Path $d | Out-Null
icacls $d /inheritance:r /grant:r 'SYSTEM:(OI)(CI)F' 'Administrators:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'ACL failed' }
$r=New-Object System.Security.Cryptography.RSACryptoServiceProvider(3072)
$r.PersistKeyInCsp=$false
[IO.File]::WriteAllText("$d\transport-private.xml",$r.ToXmlString($true))
Write-Output ('KIMI='+(@{public=$r.ToXmlString($false)}|ConvertTo-Json -Compress))
''')['public']
root=ET.fromstring(public)
def integer(tag):return int.from_bytes(base64.b64decode(root.findtext(tag)),'big')
key=rsa.RSAPublicNumbers(integer('Exponent'),integer('Modulus')).public_key()
cipher=base64.b64encode(key.encrypt(secret.read_bytes().strip(),padding.OAEP(mgf=padding.MGF1(hashes.SHA1()),algorithm=hashes.SHA1(),label=None))).decode()
model=json.loads((ROOT/'runs/azure-control/kimi-models.json').read_text())['data'][0]['id']
assert model.endswith('.modal.direct') and all(c.isalnum() or c in '.-' for c in model)
result=invoke(r'''
$d='C:\iterate-hackathon\secrets\kimi-200'
$r=New-Object System.Security.Cryptography.RSACryptoServiceProvider
$r.PersistKeyInCsp=$false
$r.FromXmlString([IO.File]::ReadAllText("$d\transport-private.xml"))
$token=[Text.Encoding]::UTF8.GetString($r.Decrypt([Convert]::FromBase64String('CIPHER'),$true))
$content="MODAL_PROXY_TOKEN=$token`nKIMI_ENDPOINT_URL=https://inference.us-west.modal.direct`nKIMI_MODEL=MODEL`n"
[IO.File]::WriteAllText("$d\modal.env",$content)
Remove-Item "$d\transport-private.xml"
Write-Output 'KIMI={"credential_provisioned":true}'
'''.replace('CIPHER',cipher).replace('KIMI_MODEL=MODEL','KIMI_MODEL='+model))
print(json.dumps(result))
