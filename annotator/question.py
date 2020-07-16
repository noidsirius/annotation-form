from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for, current_app
)
from werkzeug.exceptions import abort

from annotator.auth import login_required
from annotator.db import get_db

bp = Blueprint('question', __name__)


@bp.route('/')
@login_required
def index():
    print("SS ", current_app.url_map)
    db = get_db()
    user = g.user
    assigned_set = db.execute(
        'SELECT a.id, a.user_id, a.created, a.state'
        ' FROM assigned a'
        ' WHERE (a.user_id = ?)'
        ' ORDER BY a.created DESC'
        , (user['id'],)
    ).fetchall()
    answered_count = sum(a['state'] == 1 for a in assigned_set)
    remaining_count = sum(a['state'] == 0 for a in assigned_set)
    return render_template('question/index.html', answered_count=answered_count, remaining_count=remaining_count)


@bp.route('/next')
@login_required
def next_task():
    db = get_db()
    user = g.user
    assigned = db.execute(
        'SELECT a.id, a.user_id, a.created, a.state'
        ' FROM assigned a'
        ' WHERE (a.user_id = ? AND a.state = 0)'
        ' ORDER BY a.created DESC'
        , (user['id'],)
    ).fetchone()
    if assigned is None:
        return redirect(url_for('question.index'))
    return redirect(url_for('question.update', id=assigned['id']))


def get_assigned_datapoint(id, check_author=True, state=None):
    assigned_datapoint = get_db().execute(
        'SELECT a.id, a.user_id, a.datapoint_id, dp.description, a.state, a.body'
        ' FROM assigned a JOIN datapoint dp ON a.datapoint_id = dp.id'
        ' WHERE (a.id = ?)',
        (id,)
    ).fetchone()

    if assigned_datapoint is None:
        abort(404, "Assigned id {0} doesn't exist.".format(id))

    if state is not None and assigned_datapoint['state'] != state:
        abort(404, "Assigned id {0} is already done.".format(id))

    if check_author and assigned_datapoint['user_id'] != g.user['id']:
        abort(403)

    return assigned_datapoint


@bp.route('/<int:id>/update', methods=('GET', 'POST'))
@login_required
def update(id):
    assigned_datapoint = get_assigned_datapoint(id, state=0)
    image_path = assigned_datapoint['description']
    content_description = image_path[image_path.find('_')+1:image_path.rfind('.')]
    if request.method == 'POST':
        print("=============")
        q1_answer = request.form['q1']
        q2_answer = request.form['q2']
        error = None
        if not q1_answer or not q2_answer:
            error = 'You must answer all questions.'
        if error is not None:
            flash(error)
        else:
            db = get_db()
            answer = '%'.join([q1_answer, q2_answer])
            db.execute(
                'UPDATE assigned SET state = 1, body = ?'
                ' WHERE id = ?',
                (answer, id)
            )
            db.commit()
            return redirect(url_for('question.next_task'))
    return render_template('question/answer.html', image_path=image_path, content_description=content_description)


@bp.route('/<int:id>/clear', methods=('POST',))
@login_required
def clear(id):
    if request.method == 'POST':
        db = get_db()
        db.execute(
            'UPDATE assigned SET state = 0, body = ""'
            ' WHERE id = ?',
            (id)
        )
        db.commit()
        return redirect(url_for('question.update', id))
    return redirect(url_for('question.next_task'))



@bp.route('/<int:id>/view', methods=('GET', 'POST'))
@login_required
def view(id):
    if request.method == 'POST':
        assigned_datapoint = get_assigned_datapoint(id, check_author=True, state=1)
        db = get_db()
        db.execute(
            'UPDATE assigned SET state = 0, body = ""'
            ' WHERE id = ?',
            (id,)
        )
        db.commit()
        return redirect(url_for('question.update', id=id))
    assigned_datapoint = get_assigned_datapoint(id, check_author=False)
    image_path = assigned_datapoint['description']
    content_description = image_path[image_path.find('_')+1:image_path.rfind('.')]
    answer = None
    if assigned_datapoint['body'] is not None:
        answer = " ".join([f"Q{i+1}: {x}" for i,x in enumerate(assigned_datapoint['body'].split("%"))])

    db = get_db()
    username = db.execute('SELECT username FROM user WHERE id = ?', (assigned_datapoint['user_id'],)).fetchone()[
        'username']
    return render_template('question/answer.html', image_path=image_path, content_description=content_description,
                           is_view=True, answer=answer, username=username)


@bp.route('/user/', defaults={'username': None})
@bp.route('/user/<string:username>')
@login_required
def all_annotation(username):
    if username is None:
        username = g.user['username']
    assigned_datapoints = get_db().execute(
        'SELECT a.id, a.user_id, a.datapoint_id as dp_id, dp.description, a.state, a.body, u.username'
        ' FROM assigned a'
        ' JOIN datapoint dp ON a.datapoint_id = dp.id'
        ' JOIN user u ON a.user_id = u.id'
        ' WHERE (u.username = ?)',
        (username,)
    ).fetchall()
    return render_template('question/all_annotations.html', assigned_datapoints=assigned_datapoints)


@bp.route('/dp/<int:id>')
@login_required
def datapoint(id):
    assigned_datapoints = get_db().execute(
        'SELECT a.id, a.user_id, a.datapoint_id as dp_id, dp.description, a.state, a.body, u.username'
        ' FROM assigned a'
        ' JOIN datapoint dp ON a.datapoint_id = dp.id'
        ' JOIN user u ON a.user_id = u.id'
        ' WHERE (dp.id = ?)',
        (id,)
    ).fetchall()
    if not assigned_datapoints:
        datapoint = get_db().execute(
            'SELECT * FROM datapoint WHERE id = ?', (id,)
        ).fetchone()
        if datapoint is None:
            abort(404, "Datapoint id {0} doesn't exist.".format(id))
        datapoint = datapoint['description']
    else:
        datapoint = assigned_datapoints[0]['description']
    return render_template('question/datapoint.html', assigned_datapoints=assigned_datapoints, datapoint=datapoint)


@bp.route('/dp')
@login_required
def datapoint_list():
    datapoints = get_db().execute(
        'SELECT * FROM datapoint'
    ).fetchall()
    return render_template('question/datapoint_list.html', datapoints=datapoints)
