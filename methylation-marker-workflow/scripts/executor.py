"""Reviewed local process controller. NOT a security sandbox."""
import argparse, hashlib, json, os, re, subprocess, sys, time
from pathlib import Path

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))
def write(p, obj):
    p=Path(p); t=p.with_suffix(".tmp")
    with t.open("w",encoding="utf-8") as f:
        json.dump(obj,f,ensure_ascii=False,indent=2); f.flush(); os.fsync(f.fileno())
    for i in range(20):
        try: os.replace(t,p); return
        except PermissionError:
            if i==19: raise
            time.sleep(.05)
def validate(spec):
    if spec.get("reviewed") is not True or not spec.get("review_note"): raise ValueError("human/code review required; not a sandbox")
    if not isinstance(spec.get("argv"),list) or not spec["argv"] or not all(isinstance(v,str) for v in spec["argv"]): raise ValueError("argv must be string array")
    if not Path(spec["argv"][0]).is_absolute(): raise ValueError("absolute executable required")
    if not 0 < spec.get("timeout_seconds",0) <= 3600: raise ValueError("timeout outside local trial budget")
    if not spec.get("code") or not spec.get("outputs"): raise ValueError("code hashes and outputs required")
    for a in spec.get("inputs",[])+spec["code"]:
        if sha(a["path"]) != a["sha256"]: raise ValueError("input/code hash mismatch")
    for o in spec["outputs"]:
        if Path(o).is_absolute() or ".." in Path(o).parts: raise ValueError("output escapes attempt")
    if set(spec.get("env",{})) - {"OMP_NUM_THREADS","MKL_NUM_THREADS","OPENBLAS_NUM_THREADS"}: raise ValueError("environment key not allowed")
def stop_tree(pid):
    if os.name=="nt":
        return subprocess.run([str(Path(os.environ["SystemRoot"])/"System32/taskkill.exe"),"/PID",str(pid),"/T","/F"],capture_output=True).returncode
    import signal
    os.killpg(pid,signal.SIGKILL); return 0

def worker(job):
    state=read(job/"state.json"); spec=read(job/"spec.json"); attempt=state["attempts"][-1]; work=Path(attempt["work_dir"])
    child=None
    attempt["supervisor_pid"]=os.getpid(); write(job/"state.json",state)
    try:
        validate(spec)
        env={k:v for k,v in os.environ.items() if k.upper() in {"SYSTEMROOT","SYSTEMDRIVE","WINDIR","TEMP","TMP","PATH","PATHEXT","COMSPEC","USERPROFILE","APPDATA","LOCALAPPDATA"}}
        env.update(spec.get("env",{}))
        argv=[v.replace("{work_dir}",str(work)) for v in spec["argv"]]
        with (work/"stdout.log").open("wb") as out,(work/"stderr.log").open("wb") as err:
            kw={"creationflags":subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.CREATE_NO_WINDOW} if os.name=="nt" else {"start_new_session":True}
            child=subprocess.Popen(argv,cwd=work,env=env,stdin=subprocess.DEVNULL,stdout=out,stderr=err,**kw)
            attempt.update(child_pid=child.pid,status="running",argv=argv); state["status"]="running"; write(job/"state.json",state)
            try:
                code=child.wait(timeout=spec["timeout_seconds"]); status="passed" if code==0 else "failed"
            except subprocess.TimeoutExpired:
                cleanup=stop_tree(child.pid); attempt["tree_cleanup_exit_code"]=cleanup
                try: child.wait(timeout=10)
                except subprocess.TimeoutExpired: child.kill(); child.wait()
                code=child.returncode; status="timeout"
        outputs=[]
        if status=="passed":
            for name in spec["outputs"]:
                p=work/name
                if not p.is_file() or not p.resolve().is_relative_to(work.resolve()): raise ValueError("missing/escaped output: "+name)
                outputs.append({"path":str(p),"sha256":sha(p)})
        attempt.update(status=status,exit_code=code,outputs=outputs,finished_at=time.time())
    except Exception as e:
        attempt.update(status="recovery_required" if child is not None and child.poll() is None else "failed",exit_code=child.returncode if child is not None else None,error=str(e),finished_at=time.time())
    state["status"]=attempt["status"]; write(work/"receipt.json",attempt); write(job/"state.json",state)

def submit(root,job_id,spec,retry=False):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}",job_id): raise ValueError("invalid job id")
    validate(spec); job=Path(root).resolve()/job_id; job.mkdir(parents=True,exist_ok=True)
    lock=job/"submit.lock"
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    try:
        if (job/"spec.json").exists():
            if read(job/"spec.json") != spec: raise ValueError("duplicate id with different request")
            state=read(job/"state.json")
            if not retry:
                if state["status"]=="passed":
                    for a in state["attempts"][-1]["outputs"]:
                        if sha(a["path"])!=a["sha256"]: raise ValueError("cached output changed")
                return state
            if state["attempts"][-1].get("child_pid") and state["attempts"][-1].get("exit_code") is None: raise ValueError("ambiguous child lifecycle; manual reconciliation required")
            if state["status"] not in {"failed","timeout"}: raise ValueError("retry only terminal failed/timeout; reconcile interrupted jobs manually")
        else:
            if retry: raise ValueError("cannot retry missing job")
            write(job/"spec.json",spec); state={"status":"starting","attempts":[]}
        work=job/("attempt_%03d"%(len(state["attempts"])+1)); work.mkdir()
        state["attempts"].append({"work_dir":str(work),"status":"starting","started_at":time.time()}); state["status"]="starting"; write(job/"state.json",state)
        kw={"creationflags":subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.CREATE_NO_WINDOW} if os.name=="nt" else {"start_new_session":True}
        with (work/"supervisor.log").open("wb") as log:
            # Supervisor alone writes after spawn. No parent/worker state race.
            subprocess.Popen([sys.executable,str(Path(__file__).resolve()),"worker",str(job)],stdin=subprocess.DEVNULL,stdout=log,stderr=log,**kw)
        return state
    finally: os.close(fd); lock.unlink()

def recover(job):
    job=Path(job); state=read(job/"state.json"); work=Path(state["attempts"][-1]["work_dir"])
    receipt=read(work/"receipt.json")
    if receipt.get("work_dir")!=str(work) or receipt.get("status") not in {"passed","failed","timeout"}: raise ValueError("no matching terminal receipt; manual reconciliation required")
    if receipt.get("child_pid") and receipt.get("exit_code") is None: raise ValueError("child has no terminal exit; manual reconciliation required")
    validate(read(job/"spec.json"))
    for a in receipt.get("outputs",[]):
        if sha(a["path"])!=a["sha256"]: raise ValueError("receipt output mismatch")
    state["attempts"][-1]=receipt; state["status"]=receipt["status"]; write(job/"state.json",state); return state

def main():
    p=argparse.ArgumentParser(); p.add_argument("command",choices=["submit","retry","status","recover","worker"]); p.add_argument("path"); p.add_argument("job_id",nargs="?"); p.add_argument("spec",nargs="?"); a=p.parse_args()
    try:
        if a.command=="worker": worker(Path(a.path)); return
        if a.command=="recover": result=recover(Path(a.path)/a.job_id)
        elif a.command=="status": result=read(Path(a.path)/a.job_id/"state.json")
        else: result=submit(a.path,a.job_id,read(a.spec),a.command=="retry")
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except Exception as e: print(str(e),file=sys.stderr); sys.exit(2)
if __name__=="__main__": main()
