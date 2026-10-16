"""Run with: streamlit run app.py. No player accounts or scheduled draws."""
import html
import json
import os
from pathlib import Path
from urllib.parse import urlencode
import streamlit as st
from service import Game
from storage import Store

st.set_page_config(page_title='Tambola Circle', page_icon='🎟️', layout='wide')
st.markdown('''<style>
.stApp {background:#f6f7f2;color:#224638} h1,h2,h3{color:#214c3b!important;letter-spacing:-.04em}
[data-testid="stSidebar"]{background:#eaf0e1} [data-testid="stMetric"]{background:white;padding:18px;border:1px solid #e0e6d7;border-radius:12px}
[data-testid="stForm"]{background:white;border-color:#e0e6d7;border-radius:12px} .eyebrow{font-size:11px;letter-spacing:3px;color:#788d63;margin-top:8px}
.hero{background:#204b39;border-radius:16px;padding:26px;color:#edf1cf;display:flex;justify-content:space-between;align-items:center;margin:15px 0 24px;gap:18px}
.hero h2{color:#eef2d4!important;font-size:28px;margin:8px 0}.hero p{color:#becbad;font-size:13px}.ball{border-radius:50%;width:115px;height:115px;display:flex;align-items:center;justify-content:center;background:#e2ecac;color:#254a34;font-size:56px;font-weight:700;flex-shrink:0;box-shadow:0 12px 25px #12332250}
.board{display:grid;grid-template-columns:repeat(10,minmax(0,1fr));gap:7px;background:white;padding:18px;border:1px solid #e0e6d7;border-radius:14px}.number{padding:10px 0;text-align:center;background:#f2f4eb;border-radius:6px;color:#819070}.called{background:#dae8c8;color:#315a3f}.latest{background:#286246;color:white;font-weight:bold}
.ticket{display:grid;grid-template-columns:repeat(9,minmax(0,1fr));gap:4px;padding:12px;background:#e1e8d4;border-radius:10px}.cell{aspect-ratio:1;display:flex;align-items:center;justify-content:center;background:#fffdf2;border-radius:4px;font-weight:600;color:#355840}.blank{background:#d3ddc5}.marked{background:#2c6448;color:white}.prize{padding:14px 0;border-bottom:1px solid #e0e5d7}.prize strong{color:#315b40}.prize small{color:#8b977d}.footer{font-size:11px;color:#8e9d82;margin-top:35px;border-top:1px solid #dfe6d6;padding-top:18px}
@media(max-width:600px){.hero{padding:20px}.hero h2{font-size:22px}.ball{width:80px;height:80px;font-size:43px}.board{gap:4px;padding:10px}.number{padding:7px 0;font-size:12px}}
</style>''', unsafe_allow_html=True)

def setting(name, default=''):
    value=os.environ.get(name)
    if value is not None: return value
    try: return str(st.secrets.get(name,default))
    except FileNotFoundError: return default

@st.cache_resource
def configure(url, password_hash, signing_key):
    return Game(Store(url), password_hash, signing_key)

url=setting('DATABASE_URL')
demo=setting('TAMBOLA_DEMO')=='1'
if not url and demo:
    url='sqlite:///'+str(Path(__file__).parent/'demo.sqlite3')
if url.startswith('sqlite:///') and not demo:
    st.error('SQLite is for local demos only. Configure a PostgreSQL DATABASE_URL for hosting.');st.stop()
if not url or not setting('ADMIN_PASSWORD_HASH') or not setting('SESSION_SECRET'):
    st.title('Tambola Circle')
    st.info('The host is setting up this game. No player account will be needed.')
    with st.expander('Host setup instructions'):
        st.write('Add DATABASE_URL, ADMIN_PASSWORD_HASH and SESSION_SECRET to Streamlit app settings → Secrets. Follow DEPLOY.md in the project package. Never put database passwords in GitHub.')
    st.stop()
try:
    game=configure(url,setting('ADMIN_PASSWORD_HASH'),setting('SESSION_SECRET'))
except Exception:
    st.error('The game database is unavailable. The host should check the database connection and deployment settings.');st.stop()
if demo: st.warning('LOCAL DEMO — data is saved on this computer only. Do not use this mode on Streamlit Community Cloud.')

base=setting('PUBLIC_APP_URL').rstrip('/')

def link(token=None):
    return (base+'/' if base else '')+('?' + urlencode({'ticket':token}) if token else '')

def host_token(): return st.session_state.get('host_token','')

def action(name, **data):
    try:
        result=game.action(host_token(),name,**data)
        if name=='recover': st.session_state['recovery']=link(result)
        st.session_state['flash']='Saved successfully.'
        st.rerun()
    except ValueError as e: st.error(str(e))
    except Exception: st.error('Could not save. Refresh to check the current state before trying again.')

def ticket_view(grid, called):
    cells=''.join(f'<div class="cell {"blank" if not n else "marked" if n in called else ""}">{n or ""}</div>' for row in grid for n in row)
    st.markdown(f'<div class="ticket">{cells}</div>',unsafe_allow_html=True)
    st.caption(f'{sum(n in called for row in grid for n in row if n)} of 15 numbers marked automatically')

def board(g):
    called={d['number'] for d in g['draws']};latest=g['draws'][-1]['number'] if called else None
    cells=''.join(f'<div class="number {"latest" if n==latest else "called" if n in called else ""}">{n}</div>' for n in range(1,91))
    st.markdown(f'<div class="board">{cells}</div>',unsafe_allow_html=True)
    st.caption('Green = called · Dark green = latest · Every draw is random and non-repeating')

def hero(g):
    latest=g['draws'][-1]['number'] if g['draws'] else '—'
    title={'Registration':'Gather your circle.','Live':'Eyes on the next call.','Paused':'A little breather.','Ended':'That’s a wrap!'}[g['phase']]
    st.markdown(f'<div class="hero"><div><div class="eyebrow">ROUND {g["round"]:02} · {g["phase"].upper()}</div><h2>{title}</h2><p>{len(g["draws"])} of 90 called · Numbers change only when the host draws.</p></div><div class="ball">{latest}</div></div>',unsafe_allow_html=True)
    if g['draws']: st.caption('Recent calls: '+ '  ·  '.join(str(d['number']) for d in g['draws'][-8:][::-1]))

def prizes(g, host=False):
    for i,p in enumerate(g['prizes']):
        st.markdown(f'<div class="prize"><strong>🏆 {html.escape(p["name"])}</strong><br/><small>{"Won on call " + str(p["draw"]) if p["winners"] else "Waiting for a winning ticket"}</small></div>',unsafe_allow_html=True)
        for w in p['winners']:
            status='Distributed externally' if w['distributed'] else 'Confirmed' if w['confirmed'] else 'Awaiting host confirmation'
            st.write(f'{w["name"]} — {status}')
            if host:
                if not w['confirmed'] and st.button('Confirm winner',key=f'confirm-{i}-{w["id"]}'):
                    action('confirm',prize=i,id=w['id'])
                if w['confirmed'] and not w['distributed']:
                    delivered=st.checkbox('I have distributed this prize outside the app',key=f'delivery-{i}-{w["id"]}')
                    if st.button('Mark distributed',disabled=not delivered,key=f'paid-{i}-{w["id"]}'):
                        action('distributed',prize=i,id=w['id'])
    st.caption('All winners on the same draw are recognised. Money collection and payouts happen outside this app.')

st.sidebar.markdown('## 🎟️ tambola\n**C I R C L E**')
mode=st.sidebar.radio('Workspace',['Player','Admin'],key='workspace')
st.sidebar.divider()
st.sidebar.caption('A little luck. A lot of neighbours.\n\nNo player passwords. No automatic draws.')
if base: st.sidebar.link_button('Open shared player link',base)

if mode=='Admin':
    if not game.is_admin(host_token()):
        st.title('Your game. Your controls.')
        st.caption('Only the host signs in. Players join without accounts.')
        with st.form('admin_login'):
            password=st.text_input('Admin password',type='password',key='admin_password',max_chars=256)
            submitted=st.form_submit_button('Open admin dashboard',type='primary')
        if submitted:
            try:
                st.session_state['host_token']=game.login(password)
                st.session_state.pop('admin_password',None)
                st.rerun()
            except ValueError as e: st.error(str(e))
            except Exception: st.error('Sign-in is unavailable. Please try again shortly.')
        st.stop()
    if st.sidebar.button('Sign out of admin'):
        st.session_state.pop('host_token',None);st.rerun()
    nav=st.sidebar.radio('Admin dashboard',['Overview','Players','Tickets','Prizes','History & settings'])
    try: g=game.view(admin_token=host_token())
    except Exception: st.error('Could not load the game. Please refresh.');st.stop()
    st.markdown('<div class="eyebrow">HOST WORKSPACE</div>',unsafe_allow_html=True)
    st.title(g['title'])
    if st.session_state.get('flash'): st.success(st.session_state.pop('flash'))
    if st.session_state.get('recovery'):
        st.info('Give this private link only to its player. The previous link has been revoked.')
        st.code(st.session_state['recovery'],language=None)
        if st.button('Hide private link'): st.session_state.pop('recovery');st.rerun()
    if nav=='Overview':
        columns=st.columns(4)
        for c,label,value in zip(columns,['Players','Awaiting approval','Tickets allocated','Numbers called'],[g['counts']['total'],g['counts']['pending'],g['counts']['tickets'],len(g['draws'])]):c.metric(label,value)
        hero(g)
        a,b,c=st.columns(3)
        if g['phase']=='Registration':
            with a:
                ready=st.checkbox('Everyone is ready; lock tickets')
                if st.button('Start round',disabled=not ready,type='primary'): action('start')
        if g['phase']=='Live':
            if a.button('Draw next number',type='primary',width='stretch'):action('draw',round=g['round'],call=len(g['draws']))
            if b.button('Pause round'):action('pause')
        if g['phase']=='Paused' and a.button('Resume round',type='primary'): action('resume')
        if g['phase'] in ('Live','Paused'):
            with c:
                end=st.checkbox('Confirm early end')
                if st.button('End round',disabled=not end):action('end')
        if g['phase']=='Ended':
            if a.button('Open next round',type='primary'):action('new')
        left,right=st.columns([1.7,1])
        with left:
            st.subheader('Every number. One place.');board(g)
        with right:
            st.subheader('The winners’ circle');prizes(g)
        if st.button('Refresh dashboard'):st.rerun()
    elif nav=='Players':
        st.subheader('Your society circle')
        st.caption('Verify names and mobile numbers yourself. No OTP is sent. Collection marks are only your external records.')
        search=st.text_input('Search players')
        if not g['players']:st.info('Share the player link to receive join requests.')
        for p in g['players']:
            if search.lower() not in (p['name']+' '+p['mobile']).lower(): continue
            with st.container(border=True):
                st.write(f"**{p['name']}** · {p['mobile']} · {p['status']}")
                cols=st.columns(4)
                locked=g['phase']!='Registration'
                if cols[0].button('Approve',key='a'+p['id'],disabled=locked or p['status']=='Approved'):action('approve',id=p['id'])
                if cols[1].button('Decline',key='d'+p['id'],disabled=locked or p['status']=='Declined'):action('decline',id=p['id'])
                if cols[2].button('Replace ticket link',key='r'+p['id']):action('recover',id=p['id'])
                label='Undo collection mark' if p['collected'] else 'Mark collected externally'
                if cols[3].button(label,key='c'+p['id']):action('collected',id=p['id'],value=not p['collected'])
                st.caption('External collection: '+('Received' if p['collected'] else 'Not marked'))
    elif nav=='Tickets':
        st.subheader('A ticket for every neighbour')
        if st.button('Allocate all approved players',disabled=g['phase']!='Registration',type='primary'):action('all_tickets')
        called={d['number'] for d in g['draws']}
        cols=st.columns(2)
        people=[p for p in g['players'] if p['status']=='Approved']
        if not people:st.info('Approve players first.')
        for i,p in enumerate(people):
            with cols[i%2],st.container(border=True):
                st.write(p['name'])
                if p['ticket']:ticket_view(p['ticket'],called)
                elif st.button('Allocate ticket',key='t'+p['id'],disabled=g['phase']!='Registration'):action('allocate',id=p['id'])
    elif nav=='Prizes':
        st.subheader('Confirm winners and record distribution');prizes(g,host=True)
    else:
        st.subheader('Round history & settings')
        with st.form('title'):
            title=st.text_input('Society / game name',value=g['title'],max_chars=60)
            if st.form_submit_button('Save name',disabled=g['phase']!='Registration'):action('title',title=title)
        if base:st.code(base,language=None)
        else:st.info('Set PUBLIC_APP_URL in app Secrets after deployment to show complete invite links.')
        export={k:g[k] for k in ('title','round','phase','draws','prizes','players','log','archives')}
        st.download_button('Download host records (includes mobile numbers)',data=json.dumps(export,indent=2),file_name=f'tambola-round-{g["round"]}.json',mime='application/json')
        st.caption('Keep this host export private. It contains contact information but no access tokens.')
        st.dataframe(g['log'],width='stretch',hide_index=True)
        for old in g['archives']:
            with st.expander(f'Round {old["round"]} · {len(old["draws"])} calls'):
                prizes(old)
else:
    st.markdown('<div class="eyebrow">YOUR SOCIETY. YOUR CIRCLE.</div>',unsafe_allow_html=True)
    st.title('Your seat at the table.')
    token=st.query_params.get('ticket','')
    if token:st.session_state['player_token']=token
    token=st.session_state.get('player_token','')
    @st.fragment(run_every='5s')
    def player_screen():
        try:g=game.view(player_token=token)
        except Exception:st.warning('Reconnecting to the game…');return
        st.caption(g['title']+' · Updates every 5 seconds while this page is open')
        hero(g)
        left,right=st.columns([1.2,1])
        with left:
            p=g['player']
            if p:
                st.subheader('Hello, '+p['name'])
                if p['status']=='Pending':st.info('Your host will approve your registration shortly.')
                elif p['status']=='Declined':st.warning('Please contact the host about your registration.')
                elif p['ticket']:ticket_view(p['ticket'],{d['number'] for d in g['draws']})
                else:st.info('You’re approved. Your host will allocate your ticket next.')
                st.caption('Save your private link to return on this or another device. Anyone with it can view your ticket.')
                st.code(link(token),language=None)
                if base:st.link_button('Your private ticket link',link(token))
                st.download_button('Save my ticket link',data=link(token),file_name='my-tambola-link.txt',mime='text/plain')
            else:
                if token:st.warning('This ticket link is no longer valid. Ask your host for a replacement.')
                st.subheader('Come on in.')
                st.write('No account. No password. Just your place in the circle.')
                with st.form('join',clear_on_submit=False):
                    name=st.text_input('Your name',max_chars=50)
                    mobile=st.text_input('Mobile number',max_chars=22)
                    submit=st.form_submit_button('Join the game',type='primary',disabled=g['phase']!='Registration')
                if submit:
                    try:
                        new_token=game.join(name,mobile)
                        st.session_state['player_token']=new_token
                        st.query_params['ticket']=new_token
                        st.rerun()
                    except ValueError as e:st.error(str(e))
                    except Exception:st.error('Could not join. Please refresh or contact the host.')
                st.caption('Your number is visible only to the host. Approval is manual; no OTP is sent.')
            st.subheader('The winners’ circle');prizes(g)
        with right:
            st.subheader('Follow every call');board(g)
    player_screen()
st.markdown('<div class="footer">Made for your circle · Admin-click draws only · No in-app payments</div>',unsafe_allow_html=True)
