from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import os

from database import async_session, User, Request, Master, ConfigItem, init_db

app = FastAPI(title="Grooming Bot Admin Panel")


async def get_db() -> AsyncSession:
    """Получить сессию БД"""
    async with async_session() as session:
        yield session


# ============= API ENDPOINTS =============

@app.get("/api/requests")
async def get_requests(status: str = None, db: AsyncSession = Depends(get_db)):
    """Получить все заявки (с фильтром по статусу)"""
    try:
        stmt = select(Request).order_by(Request.created_at.desc())
        
        if status:
            stmt = stmt.where(Request.status == status)
        
        result = await db.execute(stmt)
        requests = result.scalars().all()
        
        data = []
        for req in requests:
            user_stmt = select(User).where(User.id == req.user_id)
            user_result = await db.execute(user_stmt)
            user = user_result.scalar()
            
            master_name = "не назначен"
            if req.master_id:
                master_stmt = select(Master).where(Master.id == req.master_id)
                master_result = await db.execute(master_stmt)
                master = master_result.scalar()
                master_name = master.name if master else "неизвестно"
            
            data.append({
                "id": req.id,
                "client": user.first_name if user else "?",
                "phone": user.phone if user else "?",
                "service": req.service,
                "date": req.desired_date,
                "time": req.desired_time,
                "pet": req.pet_name,
                "comment": req.comment or "",
                "status": req.status,
                "master": master_name,
                "created_at": req.created_at.strftime("%d.%m.%Y %H:%M") if req.created_at else ""
            })
        
        return data
    
    except Exception as e:
        print(f"❌ Ошибка в get_requests: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

@app.post("/api/requests/{request_id}/approve")
async def approve_request(request_id: int, master_id: int = None, db: AsyncSession = Depends(get_db)):
    """Подтвердить заявку"""
    stmt = select(Request).where(Request.id == request_id)
    result = await db.execute(stmt)
    request = result.scalar()
    
    if not request:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    
    request.status = "approved"
    if master_id:
        request.master_id = master_id
    request.updated_at = datetime.utcnow()
    
    await db.commit()
    return {"status": "ok", "message": "Заявка подтверждена"}


@app.post("/api/requests/{request_id}/reject")
async def reject_request(request_id: int, reason: str = "", db: AsyncSession = Depends(get_db)):
    """Отклонить заявку"""
    stmt = select(Request).where(Request.id == request_id)
    result = await db.execute(stmt)
    request = result.scalar()
    
    if not request:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    
    request.status = "rejected"
    request.comment = f"[ОТКЛОНЕНО] {reason}" if reason else "[ОТКЛОНЕНО]"
    request.updated_at = datetime.utcnow()
    
    await db.commit()
    return {"status": "ok", "message": "Заявка отклонена"}


@app.get("/api/masters")
async def get_masters(db: AsyncSession = Depends(get_db)):
    """Получить всех мастеров"""
    result = await db.execute(select(Master))
    masters = result.scalars().all()
    
    return [
        {
            "id": m.id,
            "name": m.name,
            "specialty": m.specialty,
            "phone": m.phone,
            "is_active": m.is_active,
            "schedule": m.schedule or {}
        }
        for m in masters
    ]


@app.post("/api/masters")
async def create_master(name: str, specialty: str, phone: str, db: AsyncSession = Depends(get_db)):
    """Создать мастера"""
    master = Master(name=name, specialty=specialty, phone=phone)
    db.add(master)
    await db.commit()
    await db.refresh(master)
    
    return {"id": master.id, "name": master.name}


@app.get("/api/requests")
async def get_requests(status: str = None, db: AsyncSession = Depends(get_db)):
    """Получить все заявки (с фильтром по статусу)"""
    try:
        stmt = select(Request).order_by(Request.created_at.desc())
        
        if status:
            stmt = stmt.where(Request.status == status)
        
        result = await db.execute(stmt)
        requests = result.scalars().all()
        
        data = []
        for req in requests:
            user_stmt = select(User).where(User.id == req.user_id)
            user_result = await db.execute(user_stmt)
            user = user_result.scalar()
            
            master_name = "не назначен"
            if req.master_id:
                master_stmt = select(Master).where(Master.id == req.master_id)
                master_result = await db.execute(master_stmt)
                master = master_result.scalar()
                master_name = master.name if master else "неизвестно"
            
            data.append({
                "id": req.id,
                "client": user.first_name if user else "?",
                "phone": user.phone if user else "?",
                "service": req.service,
                "date": req.desired_date,
                "time": req.desired_time,
                "pet": req.pet_name,
                "comment": req.comment or "",
                "status": req.status,
                "master": master_name,
                "created_at": req.created_at.strftime("%d.%m.%Y %H:%M") if req.created_at else ""
            })
        
        return data
    
    except Exception as e:
        print(f"❌ Ошибка в get_requests: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


# ============= HTML PAGES =============

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Главная панель"""
    return """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Админ-панель | Груминг-салон</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #f5f5f5;
                color: #333;
            }
            
            .container {
                max-width: 1400px;
                margin: 0 auto;
                padding: 20px;
            }
            
            header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px 20px;
                border-radius: 10px;
                margin-bottom: 30px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }
            
            h1 {
                font-size: 2.5em;
                margin-bottom: 10px;
            }
            
            .stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            
            .stat-card {
                background: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                text-align: center;
            }
            
            .stat-number {
                font-size: 2.5em;
                font-weight: bold;
                color: #667eea;
                margin: 10px 0;
            }
            
            .stat-label {
                color: #888;
                font-size: 0.9em;
            }
            
            .controls {
                display: flex;
                gap: 10px;
                margin-bottom: 20px;
                flex-wrap: wrap;
            }
            
            button {
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 1em;
                transition: all 0.3s;
            }
            
            .btn-primary {
                background: #667eea;
                color: white;
            }
            
            .btn-primary:hover {
                background: #5568d3;
                box-shadow: 0 4px 8px rgba(102, 126, 234, 0.4);
            }
            
            .btn-secondary {
                background: #f0f0f0;
                color: #333;
            }
            
            .btn-secondary:hover {
                background: #e0e0e0;
            }
            
            .btn-approve {
                background: #4caf50;
                color: white;
            }
            
            .btn-approve:hover {
                background: #45a049;
            }
            
            .btn-reject {
                background: #f44336;
                color: white;
            }
            
            .btn-reject:hover {
                background: #da190b;
            }
            
            table {
                width: 100%;
                border-collapse: collapse;
                background: white;
                border-radius: 10px;
                overflow: hidden;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            
            thead {
                background: #f8f9fa;
                border-bottom: 2px solid #ddd;
            }
            
            th {
                padding: 15px;
                text-align: left;
                font-weight: 600;
                color: #333;
            }
            
            td {
                padding: 15px;
                border-bottom: 1px solid #eee;
            }
            
            tr:hover {
                background: #f9f9f9;
            }
            
            .status {
                display: inline-block;
                padding: 5px 10px;
                border-radius: 20px;
                font-size: 0.85em;
                font-weight: 600;
            }
            
            .status-new {
                background: #fff3cd;
                color: #856404;
            }
            
            .status-approved {
                background: #d4edda;
                color: #155724;
            }
            
            .status-rejected {
                background: #f8d7da;
                color: #721c24;
            }
            
            .actions {
                display: flex;
                gap: 5px;
            }
            
            .actions button {
                padding: 5px 10px;
                font-size: 0.9em;
            }
            
            .loading {
                text-align: center;
                padding: 40px;
                color: #666;
            }
            
            .error {
                background: #f8d7da;
                color: #721c24;
                padding: 15px;
                border-radius: 5px;
                margin-bottom: 20px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>🐕 Админ-панель Груминг-салона</h1>
                <p>Управление заявками и мастерами</p>
            </header>
            
            <div class="stats" id="stats">
                <div class="stat-card">
                    <div class="stat-label">📋 Всего заявок</div>
                    <div class="stat-number" id="total">0</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">⏳ Новых</div>
                    <div class="stat-number" id="new">0</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">✅ Подтвержденных</div>
                    <div class="stat-number" id="approved">0</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">🎉 Завершено</div>
                    <div class="stat-number" id="completed">0</div>
                </div>
            </div>
            
            <div class="controls">
                <button class="btn-primary" onclick="loadRequests()">🔄 Обновить</button>
                <button class="btn-secondary" onclick="filterStatus('new')">⏳ Новые</button>
                <button class="btn-secondary" onclick="filterStatus('approved')">✅ Подтвержденные</button>
                <button class="btn-secondary" onclick="filterStatus('')">📋 Все</button>
            </div>
            
            <div id="content">
                <div class="loading">Загрузка...</div>
            </div>
        </div>
        
        <script>
            let currentFilter = '';
            
            async function loadStats() {
                try {
                    const response = await fetch('/api/stats');
                    const data = await response.json();
                    
                    document.getElementById('total').textContent = data.total;
                    document.getElementById('new').textContent = data.new;
                    document.getElementById('approved').textContent = data.approved;
                    document.getElementById('completed').textContent = data.completed;
                } catch (error) {
                    console.error('Ошибка загрузки статистики:', error);
                }
            }
            
            async function loadRequests() {
                try {
                    const url = currentFilter 
                        ? `/api/requests?status=${currentFilter}`
                        : '/api/requests';
                    
                    const response = await fetch(url);
                    const requests = await response.json();
                    
                    let html = '<table><thead><tr>';
                    html += '<th>#</th><th>Клиент</th><th>Телефон</th><th>Услуга</th>';
                    html += '<th>📅 Дата</th><th>⏰ Время</th><th>🐕 Питомец</th>';
                    html += '<th>Статус</th><th>Действия</th></tr></thead><tbody>';
                    
                    if (requests.length === 0) {
                        html += '<tr><td colspan="9" style="text-align:center; padding: 40px;">Нет заявок</td></tr>';
                    } else {
                        requests.forEach(req => {
                            const statusClass = `status status-${req.status}`;
                            html += `<tr>`;
                            html += `<td>${req.id}</td>`;
                            html += `<td>${req.client}</td>`;
                            html += `<td>${req.phone}</td>`;
                            html += `<td>${req.service}</td>`;
                            html += `<td>${req.date}</td>`;
                            html += `<td>${req.time}</td>`;
                            html += `<td>${req.pet}</td>`;
                            html += `<td><span class="${statusClass}">${req.status}</span></td>`;
                            html += `<td class="actions">`;
                            
                            if (req.status === 'new') {
                                html += `<button class="btn-approve" onclick="approveRequest(${req.id})">✅ Подтв.</button>`;
                                html += `<button class="btn-reject" onclick="rejectRequest(${req.id})">❌ Отклон.</button>`;
                            } else if (req.status === 'approved') {
                                html += `<button class="btn-secondary" onclick="completeRequest(${req.id})">✔ Завершить</button>`;
                            }
                            
                            html += `</td></tr>`;
                        });
                    }
                    
                    html += '</tbody></table>';
                    document.getElementById('content').innerHTML = html;
                } catch (error) {
                    document.getElementById('content').innerHTML = 
                        `<div class="error">Ошибка загрузки: ${error.message}</div>`;
                }
            }
            
            function filterStatus(status) {
                currentFilter = status;
                loadRequests();
            }
            
            async function approveRequest(id) {
                if (!confirm('Подтвердить заявку?')) return;
                
                try {
                    const response = await fetch(`/api/requests/${id}/approve`, {
                        method: 'POST'
                    });
                    
                    if (response.ok) {
                        alert('✅ Заявка подтверждена');
                        loadRequests();
                        loadStats();
                    }
                } catch (error) {
                    alert('Ошибка: ' + error.message);
                }
            }
            
            async function rejectRequest(id) {
                const reason = prompt('Причина отклонения:');
                if (reason === null) return;
                
                try {
                    const response = await fetch(`/api/requests/${id}/reject?reason=${reason}`, {
                        method: 'POST'
                    });
                    
                    if (response.ok) {
                        alert('❌ Заявка отклонена');
                        loadRequests();
                        loadStats();
                    }
                } catch (error) {
                    alert('Ошибка: ' + error.message);
                }
            }
            
            async function completeRequest(id) {
                if (!confirm('Отметить как завершенное?')) return;
                
                try {
                    const response = await fetch(`/api/requests/${id}/approve`, {
                        method: 'POST'
                    });
                    
                    if (response.ok) {
                        alert('✔ Заявка завершена');
                        loadRequests();
                        loadStats();
                    }
                } catch (error) {
                    alert('Ошибка: ' + error.message);
                }
            }
            
            // Загрузка при открытии страницы
            loadStats();
            loadRequests();
            
            // Автообновление каждые 10 секунд
            setInterval(() => {
                loadStats();
                loadRequests();
            }, 10000);
        </script>
    </body>
    </html>
    """
