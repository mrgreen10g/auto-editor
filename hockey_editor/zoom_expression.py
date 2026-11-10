"""Balanced lazy lookup of disjoint zoom windows; same easing and resolution."""
def expression(windows,amount):
    rows=[tuple(round(t*30) for t in w) for w in windows]
    def pulse(w):
        a,b,c,d=w
        return f'if(between(on,{a},{b}),(1-cos(PI*(on-{a})/{b-a}))/2,if(between(on,{b},{c}),1,if(between(on,{c},{d}),(1+cos(PI*(on-{c})/{d-c}))/2,0)))'
    def tree(items):
        if not items:return '0'
        if len(items)==1:return pulse(items[0])
        mid=len(items)//2
        return f'if(lt(on,{items[mid][0]}),{tree(items[:mid])},{tree(items[mid:])})'
    # Unusual overlapping user windows retain additive behavior.
    disjoint=all(rows[i][3]<rows[i+1][0] for i in range(len(rows)-1))
    value=tree(rows) if disjoint else '+'.join(map(pulse,rows)) or '0'
    return '1+'+str(amount)+'*('+value+')'
