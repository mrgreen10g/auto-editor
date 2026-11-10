"""Two independent match scans, with bounded CPU and memory use."""
from concurrent.futures import ThreadPoolExecutor
from .media import Cancelled

def scan_many(sources,cancel,log,scanner_factory=None):
    from .goals import GoalScanner,source_signature
    from .performance import scan_workers,scan_budget
    scanner_factory=scanner_factory or GoalScanner
    # Identical cache keys must never be written concurrently.
    groups={};errors=[]
    for source in sources:
        try:key=source_signature(source)
        except (OSError,ValueError) as error:
            errors.append(source.title+': '+str(error));continue
        groups.setdefault(key,[]).append(source)
    def work(group):
        if cancel.is_set():raise Cancelled('Отменено.')
        source=group[0];log('Матч: '+source.title)
        try:
            with scan_budget():
                return scanner_factory(cancel=cancel,log=log).scan(source),None
        except Cancelled:raise
        except Exception as error:return None,str(error)
    scans={}
    with ThreadPoolExecutor(max_workers=scan_workers(),thread_name_prefix='match-scan') as pool:
        for group,(result,error) in zip(groups.values(),pool.map(work,groups.values())):
            if cancel.is_set():raise Cancelled('Отменено.')
            for source in group:
                if error is not None:errors.append(source.title+': '+error)
                else:scans[source.id]=result
    return scans,errors
