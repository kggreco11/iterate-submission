$ErrorActionPreference='Stop'
$Code = @'
import base64
from pathlib import Path
p=Path(r'C:\iterate-hackathon\hc12-qualification\results\hc12-qualification\transfer.txt')
b=base64.b64decode(p.read_text())
print('TAIL85='+base64.b85encode(b[2625:]).decode())
'@
& 'C:\chemsep-benchmark\venv\Scripts\python.exe' -c $Code
