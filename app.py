from flask import Flask, render_template, request, redirect, url_for, flash, abort, jsonify
from datetime import datetime
import sqlite3
import os
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError
import pytz
from markupsafe import Markup

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ALLrise258023'  # 使用安全的随机字符串
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///notes.db'
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# 添加 nl2br 过滤器
@app.template_filter('nl2br')
def nl2br_filter(s):
    if not s:
        return ""
    return Markup(s.replace('\n', '<br>'))

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=True)
    content = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(pytz.timezone('Asia/Shanghai')))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(pytz.timezone('Asia/Shanghai')), onupdate=lambda: datetime.now(pytz.timezone('Asia/Shanghai')))

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    notes = db.relationship('Note', backref='author', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class LoginForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(), Length(min=4, max=20)])
    password = PasswordField('密码', validators=[DataRequired()])
    submit = SubmitField('登录')

class RegisterForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(), Length(min=4, max=20)])
    password = PasswordField('密码', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('确认密码', validators=[
        DataRequired(),
        EqualTo('password', message='两次输入的密码不匹配')
    ])
    submit = SubmitField('注册')

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('用户名已被使用')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for('index'))
        flash('用户名或密码错误')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(username=form.username.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('注册成功，请登录')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/')
@login_required
def index():
    notes = Note.query.filter_by(user_id=current_user.id).order_by(Note.updated_at.desc()).all()
    return render_template('index.html', notes=notes)

@app.route('/note/<int:note_id>')
@login_required
def view_note(note_id):
    note = Note.query.get_or_404(note_id)
    if note.user_id != current_user.id:
        flash('您没有权限查看这个笔记')
        return redirect(url_for('index'))
    # 直接重定向到编辑页面
    return redirect(url_for('edit_note', note_id=note_id))

@app.route('/note/<int:note_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_note(note_id):
    note = Note.query.get_or_404(note_id)
    
    # 检查权限
    if note.user_id != current_user.id:
        flash('您没有权限编辑此笔记', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        
        # 获得从表单传来的数据
        note.title = request.form.get('title')
        note.content = request.form.get('content')
        note.updated_at = datetime.now()
        
        # 提交到数据库
        db.session.commit()
        
        # 检查是否是 AJAX 请求
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': '笔记已保存'})
        
        flash('笔记已更新', 'success')
        return redirect(url_for('view_note', note_id=note.id))
    
    return render_template('edit.html', note=note)

@app.route('/note/<int:note_id>/delete', methods=['POST'])
@login_required
def delete_note(note_id):
    note = Note.query.get_or_404(note_id)
    if note.user_id != current_user.id:
        flash('您没有权限删除这个笔记')
        return redirect(url_for('index'))
    db.session.delete(note)
    db.session.commit()
    flash('笔记已删除')
    return redirect(url_for('index'))

@app.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form.get('content', '')  # 使用 get 方法，如果没有内容则默认为空字符串
        
        if not title:  # 只检查标题是否为空
            flash('标题不能为空')
            return redirect(url_for('create'))
            
        note = Note(
            title=title,
            content=content,  # content 可以为空
            user_id=current_user.id,
            created_at=datetime.now(pytz.timezone('Asia/Shanghai'))
        )
        db.session.add(note)
        db.session.commit()
        flash('笔记已创建')
        return redirect(url_for('index'))
    return render_template('create.html')


if __name__ == '__main__':
    with app.app_context():
        # 只在首次运行时创建表
        db.create_all()  # 创建表（如果不存在）
        db.session.commit()

    env = os.getenv('FLASK_ENV', 'development')
    print(f"当前环境: {env}")
    
    if env == 'production':
        ssl_context = (
            '/etc/ssl/certs/fullchain.pem',
            '/etc/ssl/certs/privkey.pem'
        )
        app.debug = True
        app.run(host='0.0.0.0', port=444, ssl_context=ssl_context)
    else:
        # 开发环境启用调试模式
        app.debug = True
        app.run(host='0.0.0.0', port=444) 


