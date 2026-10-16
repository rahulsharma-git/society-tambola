"""Pure Tambola rules; no browser state or UI dependencies."""
import secrets
from datetime import datetime, timezone

RNG = secrets.SystemRandom()
CATEGORIES = ['Early five', 'Top line', 'Middle line', 'Bottom line', 'Full house']

def now():
    return datetime.now(timezone.utc).isoformat()

def ticket():
    while True:
        rows = [set(RNG.sample(range(9), 5)) for _ in range(3)]
        if set.union(*rows) == set(range(9)):
            break
    grid = [[0] * 9 for _ in range(3)]
    for col in range(9):
        low, high = (1 if col == 0 else col * 10), (90 if col == 8 else col * 10 + 9)
        positions = [r for r in range(3) if col in rows[r]]
        for row, number in zip(positions, sorted(RNG.sample(range(low, high + 1), len(positions)))):
            grid[row][col] = number
    return grid

def round_state(number=1):
    return dict(round=number, phase='Registration', draws=[], prizes=[dict(name=n, winners=[], draw=None) for n in CATEGORIES])

def initial():
    return dict(title='Society Tambola', **round_state(), players=[], log=[], archives=[], failures=[])

def log(game, message):
    game['log'].insert(0, dict(at=now(), message=message))

def matches(grid, called, category):
    numbers = [n for row in grid for n in row if n]
    if category == 0:
        return sum(n in called for n in numbers) >= 5
    required = numbers if category == 4 else [n for n in grid[category - 1] if n]
    return all(n in called for n in required)

def draw(game):
    called = {d['number'] for d in game['draws']}
    remaining = sorted(set(range(1, 91)) - called)
    if not remaining:
        raise ValueError('All 90 numbers have been called.')
    number = secrets.choice(remaining)
    called.add(number)
    game['draws'].append(dict(number=number, at=now()))
    for index, prize in enumerate(game['prizes']):
        if prize['winners']:
            continue
        prize['winners'] = [dict(id=p['id'], name=p['name'], confirmed=False, distributed=False)
            for p in game['players'] if p['status'] == 'Approved' and p['ticket'] and matches(p['ticket'], called, index)]
        if prize['winners']:
            prize['draw'] = len(called)
    log(game, f'Call {len(called)}: number {number}.')
    if len(called) == 90:
        game['phase'] = 'Ended'
        log(game, 'All numbers called. Round ended.')
    return number
