// 世界配图统一入口：只用 webp，路径写死成 public 下的 URL。
// 之前是 `import xImage from '../../../images/x.png'` 静态导入，而 images/*.png 被 .gitignore
// 的 `*.png` 排除（仓库太大），导致 clone 下来 npm run build 直接报「找不到文件」。
// 改成 URL 字符串后，构建不再依赖本地大图；hero 缺失时用 400×225 缩略图兜底。
export const WORLD_ART = {
  '三国演义': { slug: 'sanguo', caption: '赤壁风起，天下三分' },
  '水浒传': { slug: 'shuihu', caption: '梁山泊上，聚义听潮' },
  '明代': { slug: 'mingdai', caption: '宫阙深处，风云暗涌' },
  '清代': { slug: 'qingdai', caption: '盛世帘影，旧梦将醒' },
  '西游记': { slug: 'xiyou', caption: '西行路上，妖雾重重' },
  '金瓶梅': { slug: 'jinpingmei', caption: '清河县里，浮世众生' },
  '废土末世': { slug: 'wasteland', caption: '废土荒原，文明余烬' },
  '红楼梦': { slug: 'hongloumeng', caption: '大观园里，一梦浮生' },
  '封神演义': { slug: 'fengshen', caption: '三界押注，商亡周兴' },
  '武侠江湖': { slug: 'wuxia', caption: '一柄刀，一个理由' },
  '仙侠修真': { slug: 'xianxia', caption: '从杂役到雷劫之下' },
  '大唐长安·天宝末年': { slug: 'datang', caption: '开元全盛日，一夜转衰' },
  '北宋汴京之变': { slug: 'bianjing', caption: '汴河千帆，终成旧梦' },
  '都市修真': { slug: 'urban', caption: '写字楼里，灵气初醒' },
  '日常生活': { slug: 'daily', caption: '周一早高峰，日子照旧' },
  '都市霸总': { slug: 'bazong', caption: '三十亿的价码，和一纸婚约' }
}

export const FALLBACK_SLUG = 'sanguo'

export const slugOf = (novel) => (WORLD_ART[novel] || WORLD_ART['三国演义']).slug
export const heroOf = (novel) => `/images/hero/${slugOf(novel)}.webp`
export const thumbOf = (novel) => `/images/covers/${slugOf(novel)}.webp`
export const captionOf = (novel) => (WORLD_ART[novel] || WORLD_ART['三国演义']).caption

/** 两层背景：hero 在上、缩略图在下；hero 缺失（404）时浏览器自然露出缩略图 */
export const bgLayers = (novel) => `url("${heroOf(novel)}"), url("${thumbOf(novel)}")`
