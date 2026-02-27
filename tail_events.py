import os
from collections import deque

p = 'events.jsonl'
print('exists', os.path.exists(p))
if not os.path.exists(p):
    raise SystemExit(0)

d = deque(maxlen=10)
with open(p, 'r', encoding='utf-8') as f:
    for line in f:
        d.append(line.rstrip('\n'))

print('lines', len(d))
for line in d:
    print(line)
