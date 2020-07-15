import os
import sqlite3
from werkzeug.security import generate_password_hash
import click
from flask import current_app, g
from flask.cli import with_appcontext


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row

    return g.db


def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()


def init_db():
    db = get_db()
    with current_app.open_resource('schema.sql') as f:
        db.executescript(f.read().decode('utf8'))
    ## Add a test user
    db.execute(
        'INSERT INTO user (username, password) VALUES (?, ?)',
        ('test', generate_password_hash('1234'))
    )
    # # Add questions
    # questions = ["Is it good?", "Really? Is it that good?"]
    # for question in questions:
    #     db.execute(
    #         'INSERT INTO question (description) VALUES (?)',
    #         (question,)
    #     )
    # Add datapoints
    context_images = os.path.join(current_app.static_folder, "images", "contexts")
    for file_name in os.listdir(context_images):
        if file_name.endswith(".png"):
            db.execute(
                'INSERT INTO datapoint (description) VALUES (?)',
                (file_name,)
            )
    # Assign 10 images to the test user
    test_user = db.execute('SELECT * FROM user').fetchone()
    for x in db.execute('SELECT * FROM datapoint LIMIT 10').fetchall():
        db.execute(
            'INSERT INTO assigned (user_id, datapoint_id) VALUES (?, ?)',
            (test_user['id'], x['id'])
        )
    db.commit()


@click.command('init-db')
@with_appcontext
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo('Initialized the database.')


def get_unassigned_task(user_id, count):
    db = get_db()
    q = db.execute(
        'SELECT dp.id, a.id as assigned_id'
        ' FROM datapoint dp'
        ' LEFT JOIN assigned a ON a.datapoint_id = dp.id'
        ' WHERE (a.id IS NULL OR a.user_id != ?)'
        ' GROUP BY dp.id'
        ' ORDER BY COUNT(a.id) ASC'
        ' LIMIT ?'
        , (user_id, count)
    ).fetchall()
    return q


@click.command('assign-task')
@click.argument('username')
@click.argument('task_count')
@with_appcontext
def assign_task_command(username, task_count):
    """Print FILENAME."""
    db = get_db()
    user = db.execute(
        'SELECT * FROM user WHERE username = ?', (username,)
    ).fetchone()
    if user is None:
        click.echo("The user doesn't exist.")
        return
    selected_tasks = get_unassigned_task(user['id'], task_count)

    for x in selected_tasks:
        click.echo(x.keys())
        db.execute(
            'INSERT INTO assigned (user_id, datapoint_id) VALUES (?, ?)',
            (user['id'], x['id'])
        )
    db.commit()
    click.echo(f"{len(selected_tasks)} tasks has been assigned to {username}.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(assign_task_command)

