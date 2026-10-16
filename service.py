"""Authorization, no-password player links, and host actions."""
import hashlib
import hmac
import json
import re
import secrets
import time
from copy import deepcopy
from engine import draw, log, round_state, ticket, now

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def make_password_hash(password):
    if len(password) < 12:
        raise ValueError('Use at least 12 characters for the admin password.')
    salt = secrets.token_hex(16)
    result = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 600000).hex()
    return f'pbkdf2_sha256$600000${salt}${result}'

def check_password(password, encoded):
    try:
        method, iterations, salt, expected = encoded.split('$')
        if method != 'pbkdf2_sha256' or not 100000 <= int(iterations) <= 1000000:
            return False
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), int(iterations)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False

class Game:
    def __init__(self, store, password_hash, signing_key):
        if len(signing_key) < 32:
            raise ValueError('SESSION_SECRET must have at least 32 characters.')
        self.store, self.password_hash, self.signing_key = store, password_hash, signing_key

    def is_admin(self, token):
        try:
            expires, nonce, signature = str(token).split('.')
            message = f'{expires}.{nonce}'
            expected = hmac.new(self.signing_key.encode(), message.encode(), 'sha256').hexdigest()
            return int(expires) > time.time() and hmac.compare_digest(signature, expected)
        except (ValueError, TypeError):
            return False

    def login(self, password):
        if len(password) > 256:
            raise ValueError('Password is too long.')
        def attempt(g):
            g['failures'] = [t for t in g['failures'] if t > time.time() - 300]
            if len(g['failures']) >= 10:
                return 'locked'
            if not check_password(password, self.password_hash):
                g['failures'].append(time.time())
                return 'invalid'
            g['failures'] = []
            return 'ok'
        result = self.store.mutate(attempt)
        if result != 'ok':
            raise ValueError('Try again in 5 minutes.' if result == 'locked' else 'Incorrect admin password.')
        message = f'{int(time.time()) + 8*3600}.{secrets.token_hex(12)}'
        return message + '.' + hmac.new(self.signing_key.encode(), message.encode(), 'sha256').hexdigest()

    def join(self, name, mobile):
        name = name.strip()
        mobile = re.sub(r'[\s()+-]', '', mobile)
        if not 2 <= len(name) <= 50:
            raise ValueError('Enter a name with 2–50 characters.')
        if not re.fullmatch(r'\d{8,15}', mobile):
            raise ValueError('Enter a valid mobile number.')
        token = secrets.token_urlsafe(32)
        def add(g):
            if g['phase'] != 'Registration':
                raise ValueError('Registration is closed for this round.')
            if len(g['players']) >= 200:
                raise ValueError('This game has reached its 200-player limit.')
            if any(p['mobile'] == mobile for p in g['players']):
                raise ValueError('Already registered. Use your private ticket link or ask the host to replace it.')
            g['players'].append(dict(id=secrets.token_hex(12), name=name, mobile=mobile, access=digest(token), status='Pending', ticket=None, collected=False))
            log(g, f'{name} requested to join.')
        self.store.mutate(add)
        return token

    def view(self, admin_token=None, player_token=None):
        g = self.store.read()
        host = self.is_admin(admin_token)
        p = next((p for p in g['players'] if player_token and hmac.compare_digest(p['access'], digest(player_token))), None)
        clean = {k:deepcopy(g[k]) for k in ('title', 'round', 'phase', 'draws', 'prizes')}
        clean['counts'] = dict(total=len(g['players']), pending=sum(p['status']=='Pending' for p in g['players']), approved=sum(p['status']=='Approved' for p in g['players']), tickets=sum(p['status']=='Approved' and bool(p['ticket']) for p in g['players']))
        clean['player'] = {k:deepcopy(p[k]) for k in ('id','name','status','ticket')} if p else None
        clean['admin'] = host
        clean['players'] = [{k:deepcopy(v) for k,v in p.items() if k!='access'} for p in g['players']] if host else []
        clean['log'] = deepcopy(g['log']) if host else []
        clean['archives'] = deepcopy(g['archives']) if host else []
        return clean

    def action(self, token, action, **data):
        if not self.is_admin(token):
            raise ValueError('Admin sign-in is required.')
        def mutate(g):
            p = next((p for p in g['players'] if p['id']==data.get('id')), None)
            if action in ('approve','decline','allocate','all_tickets','title') and g['phase']!='Registration':
                raise ValueError('Players and tickets are locked after the round starts.')
            if action in ('approve','decline','allocate','collected','recover') and not p:
                raise ValueError('Player not found.')
            if action == 'title':
                title = str(data.get('title','')).strip()
                if not 2<=len(title)<=60:
                    raise ValueError('Use a game name with 2–60 characters.')
                g['title']=title
                log(g,'Game name updated.')
            elif action in ('approve','decline'):
                p['status']='Approved' if action=='approve' else 'Declined'
                log(g, f"{p['name']}: {p['status']}.")
            elif action=='collected':
                p['collected']=bool(data['value'])
                log(g, f"{p['name']}: external collection marked {'received' if p['collected'] else 'not received'}.")
            elif action in ('allocate','all_tickets'):
                targets=[p] if action=='allocate' else g['players']
                existing={json.dumps(x['ticket']) for x in g['players'] if x['ticket']}
                for person in targets:
                    if person['status']=='Approved' and not person['ticket']:
                        while True:
                            grid=ticket()
                            if json.dumps(grid) not in existing: break
                        person['ticket']=grid
                        existing.add(json.dumps(grid))
                        log(g, f"Ticket allocated to {person['name']}.")
            elif action=='start':
                if g['phase']!='Registration': raise ValueError('This round already started.')
                approved=[p for p in g['players'] if p['status']=='Approved']
                if not approved or any(not p['ticket'] for p in approved):
                    raise ValueError('Approve players and allocate a ticket to every approved player first.')
                g['phase']='Live';log(g,'Round started. Tickets locked.')
            elif action=='draw':
                if g['phase']!='Live': raise ValueError('Start or resume the round first.')
                if data.get('round')!=g['round'] or data.get('call')!=len(g['draws']):
                    raise ValueError('The game changed. Refresh before drawing again.')
                draw(g)
            elif action=='pause':
                if g['phase']!='Live': raise ValueError('Only a live round can be paused.')
                g['phase']='Paused';log(g,'Round paused.')
            elif action=='resume':
                if g['phase']!='Paused': raise ValueError('The round is not paused.')
                g['phase']='Live';log(g,'Round resumed.')
            elif action=='end':
                if g['phase'] not in ('Live','Paused'): raise ValueError('No active round.')
                g['phase']='Ended';log(g,'Round ended by host.')
            elif action=='new':
                if g['phase']!='Ended': raise ValueError('End this round first.')
                g['archives'].insert(0,{k:deepcopy(g[k]) for k in ('round','draws','prizes','players','log')})
                # Never retain access credentials in exported or archived results.
                for person in g['archives'][0]['players']: person.pop('access',None)
                g.update(round_state(g['round']+1));g['log']=[]
                for person in g['players']:
                    person['ticket']=None;person['collected']=False
                log(g,'New round opened. Approved players retained; tickets and collection marks reset.')
            elif action in ('confirm','distributed'):
                index=int(data['prize'])
                if index not in range(5): raise ValueError('Invalid prize.')
                prize=g['prizes'][index]
                w=next((w for w in prize['winners'] if w['id']==data.get('id')),None)
                if not w: raise ValueError('Winning ticket not found.')
                if action=='distributed' and not w['confirmed']: raise ValueError('Confirm this winner first.')
                w['confirmed' if action=='confirm' else 'distributed']=True
                log(g,f"{prize['name']}: {w['name']} — {'confirmed' if action=='confirm' else 'distributed externally'}.")
            elif action=='recover':
                access=secrets.token_urlsafe(32);p['access']=digest(access)
                log(g,f"Private ticket link replaced for {p['name']}. Old link revoked.")
                return access
            else:
                raise ValueError('Unknown action.')
        return self.store.mutate(mutate)
