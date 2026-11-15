param([int]$Offset = 0, [int]$Length = 3500)
$ErrorActionPreference = 'Stop'
$Code = @'
import base64,gzip,json,sys
from pathlib import Path
p=Path(r'C:\iterate-hackathon\reference-replay\reference-20261114.calls.jsonl')
b=base64.b64encode(gzip.compress(p.read_bytes())).decode()
offset,length=int(sys.argv[1]),int(sys.argv[2])
print(json.dumps({'length':len(b),'offset':offset,'chunk':b[offset:offset+length]}))
'@
& 'C:\chemsep-benchmark\venv\Scripts\python.exe' -c $Code $Offset $Length
