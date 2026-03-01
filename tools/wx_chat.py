"""
微信聊天记录查询工具

依赖: pip install pywxdump
前提: 微信 PC 端必须正在运行

用法:
    python tools/wx_chat.py sync                      # 同步最新数据（含 WAL）
    python tools/wx_chat.py contacts                   # 列出最近联系人
    python tools/wx_chat.py contacts --limit 50        # 列出更多联系人
    python tools/wx_chat.py chat <昵称或备注>            # 查某人最近消息
    python tools/wx_chat.py chat <昵称或备注> --limit 100  # 查更多条
    python tools/wx_chat.py search <关键词>              # 全局搜索关键词
    python tools/wx_chat.py search <关键词> --name <昵称>  # 在某人聊天中搜索
"""

import argparse
import json
import os
import sqlite3
import sys
import io
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# 合并数据库存放目录
MERGED_DB_DIR = Path(__file__).resolve().parent.parent / "wx_decrypted.db"

# ── 微信消息类型映射 ──
MSG_TYPE_MAP = {
    1: "",           # 文本
    3: "[图片]",
    34: "[语音]",
    42: "[名片]",
    43: "[视频]",
    47: "[表情包]",
    48: "[位置]",
    49: "[链接/文件]",
    50: "[语音/视频通话]",
    10000: "[系统消息]",
    10002: "[撤回消息]",
}


def _get_wx_info():
    """从微信进程内存中提取密钥和路径"""
    from pywxdump import get_wx_info
    infos = get_wx_info()
    if not infos:
        print("错误: 无法获取微信信息，请确保微信正在运行。")
        sys.exit(1)
    return infos[0]


def _find_merged_db() -> str:
    """查找已有的合并数据库文件"""
    if not MERGED_DB_DIR.exists():
        return None
    dbs = sorted(MERGED_DB_DIR.glob("merge_*.db"), key=os.path.getmtime, reverse=True)
    return str(dbs[0]) if dbs else None


def _get_db_path() -> str:
    """获取合并数据库路径，不存在则先执行首次同步"""
    db = _find_merged_db()
    if not db:
        print("未找到已解密的数据库，正在执行首次同步...")
        return cmd_sync()
    return db


def cmd_sync() -> str:
    """同步最新微信数据（解密 + 合并，包含 WAL）"""
    info = _get_wx_info()
    key = info["key"]
    wx_path = info["wx_dir"]
    print(f"wxid:    {info['wxid']}")
    print(f"数据目录: {wx_path}")

    db_path = _find_merged_db()

    if db_path:
        # 增量同步：用 realTime.exe 合并 WAL 数据
        from pywxdump import all_merge_real_time_db
        print("正在增量同步（含 WAL 数据）...")
        result = all_merge_real_time_db(key=key, wx_path=wx_path, merge_path=db_path)
        if result and result[0]:
            db_path = result[1]
        else:
            print(f"增量同步失败: {result}，尝试全量解密...")
            db_path = None

    if not db_path:
        # 首次同步或增量失败：全量解密
        from pywxdump import decrypt_merge
        MERGED_DB_DIR.mkdir(parents=True, exist_ok=True)
        out = str(MERGED_DB_DIR)
        print("正在全量解密并合并...")
        ok, db_path = decrypt_merge(wx_path, key, out)
        if not ok:
            print(f"解密失败: {db_path}")
            sys.exit(1)

    _print_db_status(db_path)
    print("同步完成。")
    return db_path


def cmd_rebuild() -> str:
    """删除旧数据库，重新全量解密生成干净的数据库（无重复数据）"""
    info = _get_wx_info()
    key = info["key"]
    wx_path = info["wx_dir"]
    print(f"wxid:    {info['wxid']}")
    print(f"数据目录: {wx_path}")

    # 删除旧的合并数据库
    if MERGED_DB_DIR.exists():
        import shutil
        old_size = sum(f.stat().st_size for f in MERGED_DB_DIR.rglob("*") if f.is_file())
        shutil.rmtree(MERGED_DB_DIR)
        print(f"已删除旧数据库（释放 {old_size / 1024 / 1024:.1f} MB）")

    from pywxdump import decrypt_merge
    MERGED_DB_DIR.mkdir(parents=True, exist_ok=True)
    print("正在全量解密并合并...")
    ok, db_path = decrypt_merge(wx_path, key, str(MERGED_DB_DIR))
    if not ok:
        print(f"解密失败: {db_path}")
        sys.exit(1)

    _print_db_status(db_path)
    print("重建完成。")
    return db_path


def _print_db_status(db_path: str):
    """打印数据库状态信息（最新消息时间、文件大小）"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT MAX(CreateTime) FROM MSG")
    max_ts = cur.fetchone()[0]
    conn.close()
    if max_ts:
        print(f"最新消息: {datetime.fromtimestamp(max_ts).strftime('%Y-%m-%d %H:%M:%S')}")
    size_mb = os.path.getsize(db_path) / 1024 / 1024
    print(f"数据库:   {db_path} ({size_mb:.1f} MB)")
    if size_mb > 500:
        print(f"提示: 数据库已超过 500MB，建议执行 rebuild 重建以清理重复数据。")


def cmd_contacts(limit: int = 30):
    """列出最近有消息的联系人"""
    db_path = _get_db_path()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT m.StrTalker, c.NickName, c.Remark, MAX(m.CreateTime) AS LastTime,
               COUNT(*) AS MsgCount
        FROM MSG m
        LEFT JOIN Contact c ON m.StrTalker = c.UserName
        WHERE m.StrTalker NOT LIKE '%@chatroom'
          AND m.StrTalker NOT LIKE 'gh_%'
          AND m.StrTalker NOT IN ('weixin','fmessage','medianote','floatbottle','filehelper',
                                   'notifymessage','newsapp','tmessage')
        GROUP BY m.StrTalker
        ORDER BY LastTime DESC
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()

    print(f"\n{'序号':>4}  {'显示名':<20} {'最后消息时间':<18} {'消息数':>6}  wxid")
    print("-" * 85)
    for i, r in enumerate(rows, 1):
        wxid, nick, remark = r[0] or "", r[1] or "", r[2] or ""
        display = remark if remark else nick
        ts = datetime.fromtimestamp(r[3]).strftime("%Y-%m-%d %H:%M") if r[3] else ""
        count = r[4]
        print(f"{i:>4}  {display:<20} {ts:<18} {count:>6}  {wxid}")


def _resolve_wxid(conn, name: str) -> str:
    """根据昵称或备注查找 wxid"""
    cur = conn.cursor()
    # 优先精确匹配备注
    cur.execute("SELECT UserName FROM Contact WHERE Remark = ?", (name,))
    row = cur.fetchone()
    if row:
        return row[0]
    # 精确匹配昵称
    cur.execute("SELECT UserName FROM Contact WHERE NickName = ?", (name,))
    row = cur.fetchone()
    if row:
        return row[0]
    # 模糊匹配备注和昵称
    cur.execute("SELECT UserName, NickName, Remark FROM Contact WHERE Remark LIKE ? OR NickName LIKE ?",
                (f"%{name}%", f"%{name}%"))
    rows = cur.fetchall()
    if len(rows) == 1:
        return rows[0][0]
    if len(rows) > 1:
        print(f"找到多个匹配 '{name}' 的联系人:")
        for r in rows:
            display = r[2] if r[2] else r[1]
            print(f"  - {display} (wxid: {r[0]})")
        print("请使用更精确的名字。")
        sys.exit(1)
    print(f"未找到联系人: {name}")
    sys.exit(1)


def _format_msg(is_sender, ts, content, msg_type, my_label="我", other_label="对方"):
    """格式化单条消息输出"""
    time_str = datetime.fromtimestamp(ts).strftime("%m-%d %H:%M") if ts else ""
    label = MSG_TYPE_MAP.get(msg_type, f"[类型{msg_type}]")

    if msg_type != 1 and msg_type in MSG_TYPE_MAP:
        content = ""
    elif msg_type == 49 and content and len(content) > 200:
        content = content[:150] + "..."

    who = my_label if is_sender else other_label
    return f"[{time_str}] {who}: {label}{content}"


def cmd_chat(name: str, limit: int = 30):
    """查询与某人的最近聊天记录"""
    db_path = _get_db_path()
    conn = sqlite3.connect(db_path)
    wxid = _resolve_wxid(conn, name)

    # 获取联系人显示名
    cur = conn.cursor()
    cur.execute("SELECT NickName, Remark FROM Contact WHERE UserName = ?", (wxid,))
    row = cur.fetchone()
    display_name = (row[1] or row[0]) if row else name

    cur.execute("""
        SELECT IsSender, CreateTime, StrContent, Type
        FROM MSG
        WHERE StrTalker = ?
        ORDER BY CreateTime DESC
        LIMIT ?
    """, (wxid, limit))
    rows = cur.fetchall()
    conn.close()
    rows.reverse()

    print(f"\n=== {display_name} 最近 {len(rows)} 条消息 ===\n")
    for r in rows:
        line = _format_msg(r[0], r[1], r[2] or "", r[3], other_label=display_name)
        print(line)


def cmd_search(keyword: str, name: str = None, limit: int = 20):
    """搜索聊天记录中的关键词"""
    db_path = _get_db_path()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    if name:
        wxid = _resolve_wxid(conn, name)
        cur.execute("""
            SELECT m.IsSender, m.CreateTime, m.StrContent, m.Type, c.NickName, c.Remark
            FROM MSG m
            LEFT JOIN Contact c ON m.StrTalker = c.UserName
            WHERE m.StrTalker = ? AND m.StrContent LIKE ? AND m.Type = 1
            ORDER BY m.CreateTime DESC
            LIMIT ?
        """, (wxid, f"%{keyword}%", limit))
    else:
        cur.execute("""
            SELECT m.IsSender, m.CreateTime, m.StrContent, m.Type, c.NickName, c.Remark, m.StrTalker
            FROM MSG m
            LEFT JOIN Contact c ON m.StrTalker = c.UserName
            WHERE m.StrContent LIKE ? AND m.Type = 1
              AND m.StrTalker NOT LIKE '%@chatroom'
              AND m.StrTalker NOT LIKE 'gh_%'
            ORDER BY m.CreateTime DESC
            LIMIT ?
        """, (f"%{keyword}%", limit))

    rows = cur.fetchall()
    conn.close()

    scope = f" [{name}]" if name else ""
    print(f"\n=== 搜索{scope}: '{keyword}' ({len(rows)} 条结果) ===\n")
    for r in rows:
        ts = datetime.fromtimestamp(r[1]).strftime("%m-%d %H:%M") if r[1] else ""
        who_label = "我" if r[0] else (r[5] or r[4] or "对方")
        content = r[2] or ""
        if not name:
            contact = r[5] or r[4] or r[6]
            print(f"[{ts}] <{contact}> {who_label}: {content}")
        else:
            print(f"[{ts}] {who_label}: {content}")


def main():
    parser = argparse.ArgumentParser(description="微信聊天记录查询工具")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("sync", help="同步最新微信数据（增量，含 WAL）")
    sub.add_parser("rebuild", help="重建数据库（删除旧数据，全量重新解密，清理膨胀）")

    p_contacts = sub.add_parser("contacts", help="列出最近联系人")
    p_contacts.add_argument("--limit", type=int, default=30, help="显示数量（默认30）")

    p_chat = sub.add_parser("chat", help="查询与某人的聊天记录")
    p_chat.add_argument("name", help="联系人昵称或备注")
    p_chat.add_argument("--limit", type=int, default=30, help="消息条数（默认30）")

    p_search = sub.add_parser("search", help="搜索聊天记录关键词")
    p_search.add_argument("keyword", help="搜索关键词")
    p_search.add_argument("--name", help="限定在某人的聊天中搜索")
    p_search.add_argument("--limit", type=int, default=20, help="结果条数（默认20）")

    args = parser.parse_args()

    if args.command == "sync":
        cmd_sync()
    elif args.command == "rebuild":
        cmd_rebuild()
    elif args.command == "contacts":
        cmd_contacts(args.limit)
    elif args.command == "chat":
        cmd_chat(args.name, args.limit)
    elif args.command == "search":
        cmd_search(args.keyword, getattr(args, "name", None), args.limit)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
