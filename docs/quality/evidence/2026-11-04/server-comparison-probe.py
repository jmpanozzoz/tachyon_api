import sys,subprocess,time,socket,tempfile,http.client,json,random,importlib.metadata as metadata
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,'/Users/juanmanuelpanozzozenere/Projects/personal/tachyon_api')
from benchmark.run_benchmark import free_port,measure,request
from benchmark.scenarios import SCENARIOS
root='/Users/juanmanuelpanozzozenere/Projects/personal/tachyon_api'
report={'scope':'Exploratory local server comparison; same Python fallback application and threaded validating load driver. Not a production or general Rust speed claim.','python':sys.version,'versions':{p:metadata.version(p) for p in ('tachyon-api','fastapi','starlette','granian','uvicorn','orjson','msgspec')},'requests_per_scenario':2000,'concurrency':8,'repetitions':3,'warmup':100,'measurements':[]}
try:
 for repeat in range(1,4):
  targets=[(s,t) for s in ('uvicorn','uvicorn_httptools','granian') for t in ('tachyon','fastapi','asgi')];random.Random(140+repeat).shuffle(targets)
  for server,target in targets:
   port=free_port();app=f'benchmark.app_{target}:app'
   if server.startswith('uvicorn'):command=[sys.executable,'-m','uvicorn',app,'--host','127.0.0.1','--port',str(port),'--workers','1','--loop','asyncio','--http',('httptools' if server=='uvicorn_httptools' else 'h11'),'--lifespan','off','--no-access-log','--log-level','warning']
   else:command=[sys.executable,'-m','granian','--interface','asginl','--host','127.0.0.1','--port',str(port),'--workers','1','--runtime-threads','1','--loop','asyncio','--http','1','--log-level','warning',app]
   with tempfile.TemporaryFile(mode='w+') as log:
    process=subprocess.Popen(command,cwd=root,stdout=log,stderr=log)
    try:
     deadline=time.monotonic()+20
     while True:
      if process.poll() is not None:log.seek(0);raise RuntimeError(log.read())
      try:
       with socket.create_connection(('127.0.0.1',port),timeout=.1):break
      except OSError:
       if time.monotonic()>=deadline:raise RuntimeError('startup timeout')
       time.sleep(.05)
     for scenario in SCENARIOS:
      conn=http.client.HTTPConnection('127.0.0.1',port,timeout=10)
      try:
       for _ in range(100):request(conn,scenario)
      finally:conn.close()
     scenarios=list(SCENARIOS);random.Random(140+repeat).shuffle(scenarios)
     for scenario in scenarios:
      row={'server':server,'target':target,'repeat':repeat,'scenario':scenario[0],'command':command,**measure(port,scenario,2000,8)};report['measurements'].append(row)
     print(server,target,repeat,'completed',flush=True)
    finally:
     process.terminate()
     try:process.wait(timeout=10)
     except subprocess.TimeoutExpired:process.kill();process.wait()
finally:
 Path('/tmp/tachyon-server-research-three-servers.json').write_text(json.dumps(report,indent=2)+'\n')
if any(r['error_count'] for r in report['measurements']):raise SystemExit('Invalid responses')
