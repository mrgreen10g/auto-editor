"""The low-frequency mode is a whole-export ceiling, independent of cards."""
def apply(plan,frequency):
    if frequency!='low' or len(plan.inserts)<=10:return plan
    ordered=sorted(plan.inserts,key=lambda c:c.start)
    plan.inserts=[ordered[round(i*(len(ordered)-1)/9)] for i in range(10)]
    return plan
