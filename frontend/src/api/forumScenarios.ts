import type { ForumPost } from '../types/community'

// Fictional community scenarios for the explicitly disclosed experience area.
// No accounts, endorsements, replies, likes or production results are invented.
const scenarios = [
  { title: '早上进棚叶子还是湿的，先看哪几个位置？', author: '棚边老陈', category: 'question', crop: 'tomato', stage: '开花坐果期', tags: ['清晨巡棚','叶面结露'], body: '这两天早上进棚，靠东边的叶子摸着有点湿，中间看着倒还好。想先把情况记清楚再判断，怕只看中央传感器漏掉局部情况。\n\n准备在东侧和中间各选几株，记一下观察时间、叶片正反面和有没有水滴。大家平常还会看哪些地方？先不急着给它定性。' },
  { title: '滴灌管怎么编号？交接时总找不到同一根', author: '小周种瓜', category: 'experience', crop: 'muskmelon', stage: '膨果期', tags: ['滴灌','交接记录'], body: '以前交接总说“里面那根管子”，换个人就得找半天。我打算按门口往里的方向给支管编号，记录也跟着写编号，不再只写“大概东边”。\n\n标签准备选能擦写的，先试一小段，看看潮湿环境下还能不能认清。你们有没有更省事的标记办法？' },
  { title: '想比较两种通风时段，观察表怎么设计才不乱？', author: '田间笔记', category: 'research', crop: 'tomato', stage: '结果期', tags: ['通风时段','对照观察'], body: '最近在整理一个小的观察计划：固定几个点位，在不同通风时段记录温湿度和叶面状态。先把测量时间、区域和设备统一，避免今天量这边、明天量那边。\n\n还没开始做，也没有结果。最担心天气变化太大，把天气影响误算成通风效果。做过类似记录的朋友，通常怎么保留这些背景条件？' },
  { title: '甜瓜授粉日期，你们写吊牌还是直接记手机？', author: '阿禾的瓜棚', category: 'discussion', crop: 'muskmelon', stage: '坐果期', tags: ['授粉记录','田间工具'], body: '手上沾了土以后，掏手机真的不方便，纸本又容易忘在棚里。想试试按行挂小牌，回去再统一整理到手机。\n\n大家用什么方式顺手？我更在意过几天还能找到对应的果，不想记了一堆却对不上号。' },
  { title: '同一株固定角度拍照，比翻相册找照片方便', author: '番茄小满', category: 'experience', crop: 'tomato', stage: '转色期', tags: ['观察照片','固定点位'], body: '准备给几株观察植株挂个小编号，拍照时先拍编号，再拍整株和叶片近景。以前照片攒了一大堆，回头看经常分不清是不是同一株。\n\n这只是记录办法，不凭照片直接判断病害。光线和拍摄距离也尽量保持一致，后面比较才不容易看花眼。' },
  { title: '棚边几株叶缘有点卷，想先排查浇水和点位差异', author: '南坡菜园', category: 'question', crop: 'tomato', stage: '结果期', tags: ['叶片观察','根区水分'], body: '靠棚边的几株叶缘有些卷，中间暂时没看到同样情况。现在没有足够证据判断原因，不准备只凭这一点就用药。\n\n想先补上浇水时间、土壤墒情和一天里出现的时段，再拍整株与叶背。还有哪些基础信息值得一起记？' },
  { title: '一张交接单，能不能只留下真正要接着做的事？', author: '一亩青绿', category: 'discussion', crop: 'tomato', stage: '结果期', tags: ['农事交接','任务安排'], body: '想把每日交接整理成三栏：今天做了什么、还有什么没核实、明天谁接着看。工具和区域也写清楚，别让下一班重新猜。\n\n不想一上来做特别复杂的表格。大家在棚里交接时，最容易漏掉的是哪一项？' },
  { title: '换茬前的检查清单，我先从设备和记录开始列', author: '瓜棚有风', category: 'experience', crop: 'muskmelon', stage: '采收期', tags: ['换茬准备','设施检查'], body: '准备把换茬前要核对的事列成清单：旧批次记录有没有补齐、滴灌和过滤设备有没有异常、棚膜与固定件有哪些地方要检查。\n\n清园和后续处理还是要结合实际情况与当地农技指导来做。这里先聊清单怎么写，欢迎补上那些平时容易忘的小事。' },
]

export function forumScenarioPosts(): ForumPost[] {
  return scenarios.map((s,i) => {
    const at = new Date(Date.UTC(2026,9,20,9,20)-i*87*60000).toISOString()
    return { id:i+1,title:s.title,body:s.body,category:s.category,visibility:'public',status:'published',review_state:'unreviewed',
      fields:{crop:s.crop,stage:s.stage},tags:s.tags,author:s.author,author_id:-2-i,version:1,created_at:at,updated_at:at,
      accepted_comment_id:null,can_edit:false,can_moderate:false,likes:0,liked:false,bookmarked:false,comment_count:0,comments:[],assets:[] }
  })
}

export function mergeForumScenarios(posts: ForumPost[]): ForumPost[] {
  const seeds = forumScenarioPosts()
  const merged = posts.map(post => {
    const seed = seeds.find(s=>s.id===post.id&&s.author_id===post.author_id&&!post.can_edit)
    if (!seed) return post
    // Retain all browser-session interactions while replacing only the old copy.
    return {...post,title:seed.title,body:seed.body,author:seed.author,tags:seed.tags,fields:seed.fields,category:seed.category}
  })
  return [...merged,...seeds.filter(seed=>!merged.some(post=>post.id===seed.id))]
}
