# -*- coding: utf-8 -*-
import sys, os
_p = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _p)
import json, logging, uuid, re
import requests as _req
from datetime import datetime, timezone
from flask import Flask, jsonify, render_template, request
from models import RawData, db
from collectors.registry import SOURCES, fetch_all as registry_fetch

logging.basicConfig(level=logging.INFO, format="[%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("web")
app = Flask(__name__)
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db_path = os.path.join(BASE, "data", "argus.db")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///" + db_path)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "argus-lite-secret-2026")
db.init_app(app)
with app.app_context():
    db.create_all()

DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "")

# --- AI config persistence (multi-preset) ---
AI_CONFIG_PATH = os.path.join(BASE, "data", "ai_config.json")

def _load_db():
    try:
        with open(AI_CONFIG_PATH, "r") as f:
            return json.load(f)
    except:
        return {"active_key": "", "presets": {}}

def _save_db(db):
    os.makedirs(os.path.dirname(AI_CONFIG_PATH), exist_ok=True)
    with open(AI_CONFIG_PATH, "w") as f:
        json.dump(db, f, indent=2)

def load_ai_config():
    db = _load_db()
    key = db.get("active_key", "")
    if key and key in db.get("presets", {}):
        return db["presets"][key]
    # fallback: return first preset or empty
    for k, v in db.get("presets", {}).items():
        return v
    return {"api_url": "", "api_key": "", "model": ""}

def save_ai_config(cfg, name=""):
    db = _load_db()
    presets = db.setdefault("presets", {})
    if not name:
        name = db.get("active_key", "") or "default"
    presets[name] = cfg
    db["active_key"] = name
    _save_db(db)

def get_ai_presets():
    db = _load_db()
    result = []
    active = db.get("active_key", "")
    for k, v in db.get("presets", {}).items():
        result.append({"name": k, "active": k == active,
            "api_url": v.get("api_url", ""),
            "model": v.get("model", "")})
    return result

def delete_ai_preset(name):
    db = _load_db()
    if name in db.get("presets", {}):
        del db["presets"][name]
        if db.get("active_key") == name:
            db["active_key"] = next(iter(db["presets"]), "")
        _save_db(db)


def fetch_all():
    return registry_fetch()


def call_ai_api(title, content, platform):
    cfg = load_ai_config()
    api_url = cfg.get("api_url", "").rstrip("/")
    api_key = cfg.get("api_key", "") or DEEPSEEK_KEY
    model = cfg.get("model", "deepseek-chat")
    if not api_url or not api_key:
        return None
    try:
        chat_url = api_url + "/chat/completions" if not api_url.endswith("/chat/completions") else api_url
        resp = _req.post(chat_url,
            headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
            json={"model": model,
                "messages": [
                    {"role": "system", "content": "你是一个舆情分析师。分析以下新闻标题和内容，返回JSON：{\"confidence\":0-100,\"category\":\"vulnerability|threat-intel|policy|public-opinion|tech-news|other\",\"tags\":[],\"sentiment\":\"positive|negative|neutral\",\"analysis\":\"一句话分析\",\"reasoning\":\"判断理由\"}"},
                    {"role": "user", "content": "标题: " + title + "\\n来源: " + platform + "\\n内容: " + content[:2000]}
                ],
                "temperature": 0.3, "max_tokens": 500}, timeout=30)
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"].strip()
        if text.startswith("`"):
            text = text.split("\n", 1)[1].rsplit("`", 1)[0]
        return json.loads(text.strip())
    except Exception as e:
        logger.warning("AI API call failed: %s", e)
        return None

def analyze(title, content, platform):
    ai_result = call_ai_api(title, content, platform)
    if ai_result:
        return ai_result
    full = title + " " + content
    conf = 30; cat = "other"; tags = []
    if re.search(r"CVE-\d{4}-\d{4,}", full, re.I):
        conf += 30; cat = "vulnerability"; tags.append("漏洞")
    if re.search(r"(泄露|漏洞|攻击|入侵|恶意|病毒|后门|0day|ransomware|malware)", full, re.I):
        conf += 20; tags.append("安全威胁")
        if cat == "other": cat = "threat-intel"
    if re.search(r"(政策|法规|监管|立法|整改|处罚|约谈|数据安全)", full):
        conf += 20; tags.append("政策法规")
        if cat == "other": cat = "policy"
    if re.search(r"(突发|紧急|事故|灾难|抗议|曝光|争议|预警)", full):
        conf += 20; tags.append("舆情热点")
        if cat == "other": cat = "public-opinion"
    if re.search(r"(AI|人工智能|大模型|芯片|处理器|quantum)", full, re.I):
        conf += 15; tags.append("AI科技")
        if cat == "other": cat = "tech-news"
    conf = min(conf, 95)
    return {"confidence":conf,"category":cat,"tags":tags,"sentiment":"neutral",
        "analysis":"来自"+platform+"，分类"+cat+"，置信度"+str(conf)+"%。标签"+(", ".join(tags) if tags else "常规内容")+"。建议人工复核。",
        "reasoning":"规则引擎分析：扫描关键词匹配"+str(len(tags))+"个标签，综合判定为"+cat+"分类，置信度"+str(conf)+"%。"}

def save(items):
    with app.app_context():
        c = 0
        for item in items:
            if RawData.query.filter_by(url=item.get("url","")).first():
                continue
            res = analyze(item["title"], item["content"], item["platform"])
            r = RawData(source=item.get("source","direct"),platform=item["platform"],url=item.get("url",""),
                title=item.get("title",""),content=item.get("content","")[:5000],
                author=item.get("author",""),collected=datetime.now(timezone.utc),
                reason=item.get("reason",""),confidence=res.get("confidence",0),
                category=res.get("category","other"),tags=",".join(res.get("tags",[])),
                sentiment=res.get("sentiment","neutral"),ai_analysis=res.get("analysis",""),
                ai_reasoning=res.get("reasoning",""))
            db.session.add(r); c += 1
        db.session.commit()
        logger.info("saved %d items", c)
        return c

@app.route("/api/reviews")
def list_reviews():
    q = RawData.query.order_by(RawData.collected.desc())
    r = request.args.get("reviewed","pending")
    cat = request.args.get("category","")
    if r == "pending": q = q.filter(RawData.reviewed == False)
    elif r == "done": q = q.filter(RawData.reviewed == True)
    if cat: q = q.filter(RawData.category == cat)
    return jsonify([i.to_dict() for i in q.limit(200).all()])

@app.route("/api/review/<iid>", methods=["GET","POST"])
def review(iid):
    item = RawData.query.get(iid)
    if not item: return jsonify({"error":"not found"}),404
    if request.method == "GET": return jsonify(item.to_dict())
    data = request.get_json()
    act = data.get("action",""); reviewer = data.get("reviewer","admin")
    if act == "approve":
        item.reviewed=True; item.decision="approved"; item.reviewer=reviewer; item.reviewed_at=datetime.now(timezone.utc)
    elif act == "reject":
        item.reviewed=True; item.decision="rejected"; item.reviewer=reviewer; item.reviewed_at=datetime.now(timezone.utc)
        item.reject_reason = data.get("reason","")
    else: return jsonify({"error":"invalid action"}),400
    db.session.commit(); return jsonify({"status":"ok"})

@app.route("/api/collect", methods=["POST"])
def do_collect():
    try:
        items = fetch_all()
        cnt = save(items)
        return jsonify({"status":"ok","count":cnt,"message":"共采集"+str(len(items))+"条，新入库"+str(cnt)+"条"})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)}),500

@app.route("/api/stats")
def stats():
    from sqlalchemy import func
    total = RawData.query.count()
    pending = RawData.query.filter_by(reviewed=False).count()
    approved = RawData.query.filter_by(decision="approved").count()
    rejected = RawData.query.filter_by(decision="rejected").count()
    cats = db.session.query(RawData.category, func.count(RawData.id)).group_by(RawData.category).all()
    plats = db.session.query(RawData.platform, func.count(RawData.id)).group_by(RawData.platform).all()
    return jsonify({"total":total,"pending":pending,"approved":approved,"rejected":rejected,
        "by_category":{s or "other":c for s,c in cats},"by_platform":{s or "unknown":c for s,c in plats}})

@app.route("/api/ai-config", methods=["GET"])
def get_ai_config():
    cfg = load_ai_config()
    presets = get_ai_presets()
    return jsonify({"api_url": cfg.get("api_url", ""), "api_key": "***" if cfg.get("api_key") else "", "model": cfg.get("model", ""), "presets": presets})

@app.route("/api/ai-config", methods=["POST"])
def set_ai_config():
    data = request.get_json() or {}
    cfg = load_ai_config()
    if "api_url" in data:
        cfg["api_url"] = data["api_url"].strip().rstrip("/")
    if "api_key" in data and data["api_key"] and data["api_key"] != "***":
        cfg["api_key"] = data["api_key"].strip()
    if "model" in data:
        cfg["model"] = data["model"].strip()
    name = data.get("name", "").strip() or ""
    save_ai_config(cfg, name)
    return jsonify({"status": "ok", "api_url": cfg["api_url"], "model": cfg["model"], "name": name or list(_load_db().get("presets", {}).keys())[-1:][0] if _load_db().get("presets") else ""})

@app.route("/api/ai-test", methods=["POST"])
def test_ai_config():
    data = request.get_json() or {}
    u = data.get("api_url", "").strip().rstrip("/")
    k = data.get("api_key", "").strip()
    m = data.get("model", "deepseek-chat").strip()
    if not u or not k:
        return jsonify({"status": "error", "message": "缺少 API 地址或密钥"}), 400
    try:
        chat_url = u + "/chat/completions" if not u.endswith("/chat/completions") else u
        resp = _req.post(chat_url,
            headers={"Authorization": "Bearer " + k, "Content-Type": "application/json"},
            json={"model": m, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 5},
            timeout=15)
        resp.raise_for_status()
        return jsonify({"status": "ok", "message": "连接成功", "model": m})
    except _req.exceptions.ConnectTimeout:
        return jsonify({"status": "error", "message": "连接超时，请检查 API 地址"}), 502
    except _req.exceptions.ConnectionError:
        return jsonify({"status": "error", "message": "无法连接，请检查 API 地址和网络"}), 502
    except _req.exceptions.HTTPError as e:
        return jsonify({"status": "error", "message": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}), 502
    except Exception as e:
        return jsonify({"status": "error", "message": f"请求异常: {str(e)[:200]}"}), 502

@app.route("/api/ai-presets", methods=["GET"])
def list_presets():
    return jsonify({"presets": get_ai_presets()})

@app.route("/api/ai-presets/<name>", methods=["DELETE"])
def remove_preset(name):
    delete_ai_preset(name)
    return jsonify({"status": "ok"})

@app.route("/api/ai-load/<name>", methods=["POST"])
def load_preset(name):
    db = _load_db()
    if name not in db.get("presets", {}):
        return jsonify({"status": "error", "message": "配置不存在"}), 404
    db["active_key"] = name
    _save_db(db)
    cfg = db["presets"][name]
    return jsonify({"status": "ok", "api_url": cfg.get("api_url", ""), "model": cfg.get("model", "")})

@app.route("/api/collectors")
def collectors():
    return jsonify({"collectors":[{"id":sid,"name":cfg["name"],"rsshub":cfg.get("rsshub",""),"fallback":bool(cfg.get("fallback"))} for sid,cfg in SOURCES.items()],"deepseek":bool(DEEPSEEK_KEY)})

@app.route("/")
def index():
    return render_template("dashboard.html")

if __name__ == "__main__":
    host = os.getenv("HOST","0.0.0.0"); port = int(os.getenv("PORT","8090"))
    logger.info("=== ARGUS-Lite 启动 ===")
    logger.info("Sources: %d configured (RSSHub + fallback)", len(SOURCES))
    logger.info("DeepSeek: %s", "已配置" if DEEPSEEK_KEY else "未配置(规则兜底)")
    logger.info("访问: http://localhost:%d", port)
    app.run(host=host, port=port, debug=False, use_reloader=False)