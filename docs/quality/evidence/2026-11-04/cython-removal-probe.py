import subprocess,tarfile,tempfile,io,json,hashlib
from pathlib import Path
root=Path('/Users/juanmanuelpanozzozenere/Projects/personal/tachyon_api')
target=Path(tempfile.mkdtemp(prefix='tachyon-no-cython-probe-'))
raw=subprocess.check_output(['git','archive','origin/main'],cwd=root)
with tarfile.open(fileobj=io.BytesIO(raw)) as a:a.extractall(target,filter='data')
removed=[]
for pattern in ('*.pyx','*.pxd'):
 for p in (target/'tachyon_api').rglob(pattern):removed.append(str(p.relative_to(target)));p.unlink()
p=target/'setup.py';s=p.read_text();start=s.index('extensions = []');end=s.index('\nsetup(',start);s=s[:start]+'extensions = []\n'+s[end:];p.write_text(s)
p=target/'pyproject.toml';lines=[s for s in p.read_text().splitlines() if not s.lstrip().startswith('cython =') and 'path = "tachyon_api/**/*.pyx"' not in s and 'path = "tachyon_api/**/*.pxd"' not in s];s='\n'.join(lines)+'\n';s=s.replace('fast = ["cython"]','fast = []').replace(', "cython>=3.0"','');p.write_text(s)
py='/tmp/tachyon-review-current-env/bin/python';steps=[]
for name,cmd in [('tests',[py,'-m','pytest','tests','example/tests','-q']),('build',[py,'-m','build','--wheel','--sdist','--outdir',str(target/'artifacts')])]:
 log=target/f'{name}.log'
 with log.open('w') as f:r=subprocess.run(cmd,cwd=target,stdout=f,stderr=subprocess.STDOUT)
 steps.append({'step':name,'returncode':r.returncode,'log':str(log)})
 if r.returncode:break
files={str(p.relative_to(target)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (target/'tachyon_api').rglob('*.py')}
report={'scope':'Disposable removal experiment, not implemented migration; build/release gates still require adaptation','source_revision':subprocess.check_output(['git','rev-parse','origin/main'],cwd=root,text=True).strip(),'directory':str(target),'removed':removed,'python_runtime_files_unchanged':all(hashlib.sha256((root/p).read_bytes()).hexdigest()==sha for p,sha in files.items()),'steps':steps,'runtime_python_files':len(files)}
Path('/tmp/tachyon-cython-removal-probe.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
