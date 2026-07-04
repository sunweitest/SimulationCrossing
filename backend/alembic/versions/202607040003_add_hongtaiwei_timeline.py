"""add characters for 洪太尉访道 timeline (水浒传 opening)

Revision ID: 202607040003
Revises: 202607040002
Create Date: 2026-07-04 19:50:00
"""
from alembic import op
import sqlalchemy as sa

revision = "202607040003"
down_revision = "202607040002"
branch_labels = None
depends_on = None

NEW_CHARACTERS = [
    ("水浒传", "洪信", "男性", 45, "太尉",
     "当朝太尉，奉旨前往江西龙虎山请天师禳灾。好奇心重且刚愎自用，不顾真人劝阻，执意打开伏魔殿，放出三十六天罡、七十二地煞——从此天下大乱。",
     50,
     [("洪太尉访道", "京师瘟疫横行，仁宗天子命你前往江西龙虎山请张天师禳灾。你本不以为然——一个道士，能有什么真本事？",
       "东京皇城外，宋仁宗将圣旨亲手交予你：'洪爱卿，此番前往龙虎山，务必将天师请来。千万百姓的性命，系于你一身。'你跪地接旨，心中却想：不过走一趟罢了。")]),

    ("水浒传", "张天师", "男性", 60, "虚靖先生",
     "龙虎山嗣汉天师府第三十代天师张继先，号虚靖先生。道法高深，预知未来，早已算到洪太尉此行将酿成大祸——但他知道，这是天数。",
     65,
     [("洪太尉访道", "京师有旨，太尉洪信要来请你禳灾。但你掐指一算，已知此行真正目的不在瘟疫——而是伏魔殿。",
       "龙虎山天师府，你端坐蒲团。道童匆匆来报：'天师，洪太尉已到上清宫！'你睁开眼，手中拂尘轻挥：'天命不可违。那伏魔殿中的一百零八魔星，该出世了。'")]),

    ("水浒传", "清风", "男性", 16, "道童",
     "龙虎山上清宫道童，年幼天真，负责引导洪太尉参观。无意中成了打开伏魔殿的'帮凶'。",
     35,
     [("洪太尉访道", "你是上清宫最机灵的道童。今日来了个大人物——洪太尉。住持让你引他游览，你不敢怠慢。但你不知道，这位大人将做出何等惊人之举。",
       "上清宫殿前，你快步迎上洪太尉：'大人，这边请。上清宫供的是三清祖师，最是灵验。'你一边引路一边偷偷打量他——这位京城来的大官，眉头紧锁，似乎心事重重。")]),

    ("水浒传", "赵祯", "男性", 50, "宋仁宗",
     "北宋第四位皇帝，年号嘉祐。仁义之君，在位四十二年。因京师瘟疫肆虐、百姓苦不堪言，命洪信前往龙虎山请天师祈福。",
     70,
     [("洪太尉访道", "京师瘟疫横行，每天都有百姓死于疾疫。你斋戒沐浴，祭告天地，但似乎无济于事。有人奏报：龙虎山张天师能禳灾——你将全部希望押在了这道圣旨上。",
       "东京皇宫垂拱殿，你望着御案上堆积如山的疫情奏报。户部尚书跪地奏道：'陛下，京城每日死者不下数百，请速决断！'你提笔写下圣旨：'宣太尉洪信，即刻前往江西龙虎山，请张天师进京禳灾。'")]),
]


def upgrade():
    conn = op.get_bind()
    for novel, name, gender, age, rank, bg, pts, timelines in NEW_CHARACTERS:
        existing = conn.execute(
            sa.text("SELECT id FROM preset_characters WHERE novel = :novel AND name = :name"),
            {"novel": novel, "name": name}
        ).fetchone()

        if existing:
            char_id = existing[0]
        else:
            row = conn.execute(
                sa.text(
                    "INSERT INTO preset_characters (novel, name, gender, age, rank, background, starting_points) "
                    "VALUES (:novel, :name, :gender, :age, :rank, :bg, :pts) RETURNING id"
                ),
                {"novel": novel, "name": name, "gender": gender, "age": age, "rank": rank, "bg": bg, "pts": pts}
            ).fetchone()
            char_id = row[0]

        for tl, tl_bg, tl_scene in timelines:
            tl_existing = conn.execute(
                sa.text("SELECT id FROM character_timelines WHERE character_id = :cid AND timeline = :tl"),
                {"cid": char_id, "tl": tl}
            ).fetchone()
            if not tl_existing:
                conn.execute(
                    sa.text(
                        "INSERT INTO character_timelines (character_id, timeline, background, initial_scene) "
                        "VALUES (:cid, :tl, :bg, :scene)"
                    ),
                    {"cid": char_id, "tl": tl, "bg": tl_bg, "scene": tl_scene}
                )


def downgrade():
    conn = op.get_bind()
    for novel, name, *_ in NEW_CHARACTERS:
        row = conn.execute(
            sa.text("SELECT id FROM preset_characters WHERE novel = :novel AND name = :name"),
            {"novel": novel, "name": name}
        ).fetchone()
        if row:
            conn.execute(sa.text("DELETE FROM character_timelines WHERE character_id = :cid"), {"cid": row[0]})
            conn.execute(sa.text("DELETE FROM preset_characters WHERE id = :cid"), {"cid": row[0]})
