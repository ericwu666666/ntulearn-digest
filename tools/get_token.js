// 取 NTULearn token 的两种方法（都只在你自己的浏览器里运行，不会发到任何地方）
//
// 方法一：控制台
//   1. 用 Chrome / Edge 打开 https://ntulearn.ntu.edu.sg 并登录
//   2. 按 F12（Mac 上是 ⌥⌘J）打开 Console，粘贴下面这一行，回车
//   3. token 已复制到剪贴板，回到终端运行：ntulearn auth --clipboard
copy(JSON.parse(atob(sessionStorage.getItem('fnds.token.normal'))).accessToken)

// 方法二：书签小工具
//   新建一个书签，网址填下面整行（从 javascript: 开始），在 NTULearn 页面上点它即可复制。
// javascript:(()=>{try{const t=JSON.parse(atob(sessionStorage.getItem('fnds.token.normal'))).accessToken;navigator.clipboard.writeText(t).then(()=>alert('NTULearn token 已复制，大约 1 小时内有效'),()=>prompt('自动复制失败，请手动复制：',t))}catch(e){alert('没找到 token：请先在这个标签页打开 NTULearn 并登录')}})();
//
// token 大约 1 小时过期，过期后重新复制即可。不要把 token 发给别人或提交到 GitHub。
