#! /usr/bin/python3

# Количество партиций
NUMPARTS=500
# Допустимое максимальное отклонение количества партиций
VAR_MAX=0.1

BASE64SYMBOLS="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+/"
SYMBOLS="".join(sorted(BASE64SYMBOLS))
NUMSYMS=len(SYMBOLS)
NUMCHARS=1 + round((1.0 * NUMPARTS) ** (1.0 / NUMSYMS))
MAXVAL=NUMSYMS ** NUMCHARS
ADJUST=(1.0 * MAXVAL) / (1.0 * NUMPARTS)

print("NUMSYMS=", NUMSYMS)
print("SYMBOLS=", SYMBOLS)
print("NUMCHARS=", NUMCHARS)
print("ADJUST=", ADJUST)

def makeOut(pos: int) -> str:
    ret = ''
    cur = round(pos * ADJUST)
    for i in range(NUMCHARS):
        tmp = cur % NUMSYMS
        cur = cur // NUMSYMS
        ret = SYMBOLS[tmp:tmp+1] + ret
    return ret

OUT=[]
for i in range(NUMPARTS-1):
    OUT.append(makeOut(i+1))

print(OUT)
