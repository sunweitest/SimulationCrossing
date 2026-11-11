// 世界环境音床（共用公用库 frontend/public/audio/amb/）
// 每条 20 秒循环、64kbps 单声道、约 156KB；生成脚本 scripts/gen_ambience.py
// 新增世界时：在 scripts/prompts/ambience.json 加一条 → 跑脚本 → 这里补一行映射
export const WORLD_AMBIENCE = {
  '三国演义': '/audio/amb/amb-sanguo.mp3',
  '水浒传': '/audio/amb/amb-shuihu.mp3',
  '红楼梦': '/audio/amb/amb-honglou.mp3',
  '金瓶梅': '/audio/amb/amb-jinpingmei.mp3',
  '明代': '/audio/amb/amb-ming.mp3',
  '清代': '/audio/amb/amb-qing.mp3',
  '西游记': '/audio/amb/amb-xiyou.mp3',
  '封神演义': '/audio/amb/amb-fengshen.mp3',
  '废土末世': '/audio/amb/amb-wasteland.mp3',
  '武侠江湖': '/audio/amb/amb-wuxia.mp3',
  '仙侠修真': '/audio/amb/amb-xianxia.mp3',
  '大唐长安·天宝末年': '/audio/amb/amb-tang.mp3',
  '北宋汴京之变': '/audio/amb/amb-song.mp3',
  '都市霸总': '/audio/amb/amb-bazong.mp3',
  '都市修真': '/audio/amb/amb-dushi-xiuzhen.mp3',
  '日常生活': '/audio/amb/amb-daily.mp3',
}

export const AMBIENCE_VOLUME = 0.32
export const AMBIENCE_DUCKED = 0.10
