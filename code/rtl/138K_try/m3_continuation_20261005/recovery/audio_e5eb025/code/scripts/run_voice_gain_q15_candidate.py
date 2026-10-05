"""Independent candidate-Q15 vectors; no production amplitude decision."""
from pathlib import Path
import random
import subprocess
root=Path(__file__).resolve().parents[2]
stage=root/'code/output/t009_gain_candidate';stage.mkdir(parents=True,exist_ok=True)
rows=[]
for wave in range(-32768,32768):
    for env in (0,1,16384,32766,32767):rows.append((wave,env,(wave*env)//32768))
rng=random.Random(20260930)
for _ in range(10000):
    w=rng.randrange(-32768,32768);e=rng.randrange(32768);rows.append((w,e,(w*e)//32768))
vectors=stage/'vectors.txt';vectors.write_text(''.join(f'{w} {e} {v}\n' for w,e,v in rows),encoding='ascii')
cad=Path('D:/Gowin/oss-cad-suite');q=lambda p:'"'+str(p)+'"'
bat=stage/'run.bat';bat.write_text('@echo off\r\ncall '+q(cad/'environment.bat')+' >nul\r\n'+q(cad/'bin/iverilog.exe')+' -g2012 -s tb_voice_gain_q15_candidate -o '+q(stage/'tb.vvp')+' '+q(root/'code/rtl/board/voice_gain_q15_candidate.sv')+' '+q(root/'code/tb/board/tb_voice_gain_q15_candidate.sv')+'\r\nif errorlevel 1 exit /b 1\r\n'+q(cad/'bin/vvp.exe')+' '+q(stage/'tb.vvp')+' '+q('+VECTORS='+str(vectors))+'\r\nexit /b %errorlevel%\r\n',encoding='ascii')
p=subprocess.run(['cmd.exe','/c',str(bat)],cwd=stage,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
(stage/'run.log').write_text(p.stdout+p.stderr,encoding='utf-8');print(p.stdout);print('Vector count:',len(rows))
raise SystemExit(p.returncode if p.returncode else (0 if f'PASS voice_gain_q15_candidate vectors={len(rows)}' in p.stdout else 1))