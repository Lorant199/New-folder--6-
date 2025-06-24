import os
import uuid
import json
from json import JSONDecodeError
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, g, send_from_directory
)
from werkzeug.utils import secure_filename


app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = 'replace-with-a-secure-random-key'


BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

DATA_FILES = {
    'users':            os.path.join(DATA_DIR, 'users.json'),
    'projects':         os.path.join(DATA_DIR, 'projects.json'),
    'comments':         os.path.join(DATA_DIR, 'comments.json'),
    'private_messages': os.path.join(DATA_DIR, 'private_messages.json'),
    'events':           os.path.join(DATA_DIR, 'events.json'),
    'learning':         os.path.join(DATA_DIR, 'learning.json'),
}

def load_data(name):
    path = DATA_FILES[name]
    if not os.path.exists(path):
        with open(path, 'w') as f:
            json.dump([], f)
        return []
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (JSONDecodeError, ValueError):
        with open(path, 'w') as f:
            json.dump([], f)
        return []

def save_data(name, data):
    path = DATA_FILES[name]
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'pdf','doc','docx','xls','xlsx','ppt','pptx','txt','png','jpg','jpeg','gif'}

def allowed_file(fname):
    return '.' in fname and fname.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS


@app.context_processor
def inject_user():
    return {'user': g.get('user')}

def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        g.user = session['user']
        return f(*args, **kwargs)
    return wrapped

@app.before_request
def load_logged_in_user():
    g.user = session.get('user')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        users = load_data('users')
        uname = request.form['username'].strip()
        pwd   = request.form['password']
        role  = request.form.get('role', 'employee')    
        if any(u['username'] == uname for u in users):
            flash('Username taken', 'error')
        else:
            users.append({
                'id':       str(uuid.uuid4()),
                'username': uname,
                'password': pwd,
                'role':     role                     
            })
            save_data('users', users)
            flash('Registered! Please log in.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        users = load_data('users')
        uname = request.form['username'].strip()
        pwd = request.form['password']
        user = next((u for u in users if u['username']==uname and u['password']==pwd), None)
        if user:
            session.clear()
            session['user'] = user
            flash(f"Welcome back, {uname}!", 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid username or password', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/')
@login_required
def dashboard():
    projects = load_data('projects')
    users = load_data('users')
    users_dict = {u['id']:u for u in users}
    total = len(projects)
    by_status = {'pending':0,'approved':0,'rejected':0}
    by_priority = {'urgent':0,'medium':0,'regular':0}
    for p in projects:
        by_status[p.get('status','pending')] += 1
        by_priority[p.get('priority','medium')] += 1
    stats = {'total': total,'by_status': by_status,'by_priority': by_priority}
    return render_template('dashboard.html', projects=projects,
                        users_dict=users_dict, stats=stats)


@app.route('/projects/new', methods=['GET','POST'])
@login_required
def create_project():
    if request.method=='POST':
        projects = load_data('projects')
        projects.append({
            'id':str(uuid.uuid4()),
            'title':request.form['title'],
            'description':request.form.get('description',''),
            'priority':request.form.get('priority','medium'),
            'creator_id':g.user['id'],
            'status':'pending',
            'open_to_all':'open_to_all' in request.form,
            'assignees':[], 'participants':[]
        })
        save_data('projects', projects)
        flash('Project created!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('create_project.html')

@app.route('/projects/<pid>', methods=['GET','POST'])
@login_required
def project_detail(pid):
    projects = load_data('projects')
    comments = load_data('comments')
    users    = load_data('users')
    proj = next((p for p in projects if p['id']==pid), None)
    if not proj:
        flash('Not found.', 'error'); return redirect(url_for('dashboard'))
    proj.setdefault('open_to_all',False)
    proj.setdefault('assignees',[]) 
    proj.setdefault('participants',[])
    save_data('projects', projects)
    if request.method=='POST':
        if 'join' in request.form and g.user['role']=='employee':
            uid=g.user['id']
            if uid not in proj['participants']:
                proj['participants'].append(uid)
                save_data('projects', projects)
                flash('You joined!', 'success')
        elif 'action' in request.form and g.user['role']=='manager':
            proj['status']=request.form['action']
            save_data('projects', projects)
            flash(f"Project {proj['status']}.", 'success')
        elif 'assign-submit' in request.form and g.user['role']=='manager':
            proj['open_to_all']='open_to_all' in request.form
            proj['assignees']=request.form.getlist('assignees')
            proj['participants']=[u for u in proj['participants']
                                  if proj['open_to_all'] or u in proj['assignees']]
            save_data('projects', projects)
            flash('Assignments updated.', 'success')
        elif 'comment' in request.form and request.form['comment'].strip():
            comments.append({
                'id':str(uuid.uuid4()),
                'project_id':pid,
                'user_id':g.user['id'],
                'text':request.form['comment'].strip(),
                'timestamp':datetime.utcnow().isoformat()+'Z'
            })
            save_data('comments', comments)
        return redirect(url_for('project_detail', pid=pid))
    proj_comments=[c for c in comments if c['project_id']==pid]
    return render_template('project_detail.html',
                           project=proj,
                           comments=proj_comments,
                           users=users,
                           users_dict={u['id']:u for u in users})


@app.route('/chat/users')
@login_required
def chat_users():
    users=load_data('users')
    others=[u for u in users if u['id']!=g.user['id']]
    return jsonify([{'id':u['id'],'username':u['username'],'role':u['role']} for u in others])

@app.route('/chat/messages/<other_id>', methods=['GET','POST'])
@login_required
def private_chat(other_id):
    msgs=load_data('private_messages')
    if request.method=='POST':
        data=request.get_json() or {}
        t=data.get('text','').strip()
        if t:
            msgs.append({'id':str(uuid.uuid4()),
                         'from':g.user['id'],
                         'to':other_id,
                         'text':t,
                         'timestamp':datetime.utcnow().isoformat()+'Z'})
            save_data('private_messages', msgs)
        return jsonify(msgs),201
    conv=[m for m in msgs if
          (m['from']==g.user['id'] and m['to']==other_id) or
          (m['from']==other_id and m['to']==g.user['id'])]
    return jsonify(conv)

@app.route('/events', methods=['GET','POST'])
@login_required
def events():
    evs=load_data('events')
    if request.method=='POST':
        data=request.get_json() or {}
        title=data.get('title','').strip()
        date=data.get('date')
        if title and date:
            ev={'id':str(uuid.uuid4()),
                'title':title,'start':date,'end':date}
            evs.append(ev); save_data('events', evs)
            return jsonify(ev),201
        return jsonify({'error':'Invalid data'}),400
    return jsonify(evs)

@app.route('/learning')
@login_required
def learning():
    items=load_data('learning')
    approved=[i for i in items if i.get('status')=='approved']
    pending=[i for i in items if i.get('status')=='pending'] if g.user['role']=='manager' else []
    return render_template('learning.html', approved=approved, pending=pending)

@app.route('/learning/new', methods=['GET', 'POST'])
@login_required
def create_learning():
    if request.method == 'POST':
        items = load_data('learning')
        items.append({
            'id': str(uuid.uuid4()),
            'title': request.form['title'],
            'url': request.form['url'],
            'description': request.form['description'],
            'category': request.form['category'],
            'status': 'pending',
            'creator_id': g.user['id']
        })
        save_data('learning', items)
        flash('Submitted for approval!', 'success')
        return redirect(url_for('learning'))
    return render_template('create_learning.html')


@app.route('/learning/approve/<item_id>')
@login_required
def approve_learning(item_id):
    if g.user['role']!='manager':
        flash('Not authorized','error'); return redirect(url_for('learning'))
    items=load_data('learning')
    for it in items:
        if it['id']==item_id: it['status']='approved'; break
    save_data('learning', items)
    flash('Approved!','success')
    return redirect(url_for('learning'))

@app.route('/learning/reject/<item_id>')
@login_required
def reject_learning(item_id):
    if g.user['role']!='manager':
        flash('Not authorized','error'); return redirect(url_for('learning'))
    items=load_data('learning')
    for it in items:
        if it['id']==item_id: it['status']='rejected'; break
    save_data('learning', items)
    flash('Rejected.','info')
    return redirect(url_for('learning'))

@app.route('/files')
@login_required
def files():
    names=sorted(os.listdir(UPLOAD_FOLDER))
    return render_template('files.html', files=names)

@app.route('/files/upload', methods=['POST'])
@login_required
def upload_file():
    f=request.files.get('file')
    if not f or f.filename=='' or not allowed_file(f.filename):
        flash('Invalid file.','error'); return redirect(url_for('files'))
    fn=secure_filename(f.filename)
    f.save(os.path.join(UPLOAD_FOLDER, fn))
    flash(f'Uploaded \"{fn}\".','success')
    return redirect(url_for('files'))

@app.route('/files/download/<filename>')
@login_required
def download_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

@app.route('/files/delete/<filename>')
@login_required
def delete_file(filename):
    if g.user['role']!='manager':
        flash('Not auth','error'); return redirect(url_for('files'))
    p=os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(p): os.remove(p); flash(f'Deleted \"{filename}\".','success')
    else: flash('Not found','error')
    return redirect(url_for('files'))

if __name__=='__main__':
    app.run(debug=True)
