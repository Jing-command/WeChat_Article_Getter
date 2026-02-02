async function getActiveTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  return tabs[0];
}

function extractTokenFromUrl(url) {
  try {
    const u = new URL(url);
    return u.searchParams.get("token") || "";
  } catch {
    return "";
  }
}

function getCookies(domain) {
  return new Promise((resolve) => {
    chrome.cookies.getAll({ domain }, (cookies) => resolve(cookies || []));
  });
}

function toCookieString(cookies) {
  return cookies.map((c) => `${c.name}=${c.value}`).join("; ");
}

function showSuccessNotification() {
  // 创建成功通知
  const notification = document.createElement("div");
  notification.style.cssText = `
    position: fixed;
    top: 10px;
    left: 50%;
    transform: translateX(-50%);
    background: #28a745;
    color: white;
    padding: 12px 20px;
    border-radius: 6px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    font-weight: bold;
    z-index: 9999;
    animation: slideDown 0.3s ease-out;
  `;
  notification.textContent = "✅ 已复制到剪贴板！";
  
  document.body.appendChild(notification);
  
  // 添加动画
  const style = document.createElement("style");
  style.textContent = `
    @keyframes slideDown {
      from {
        opacity: 0;
        transform: translateX(-50%) translateY(-20px);
      }
      to {
        opacity: 1;
        transform: translateX(-50%) translateY(0);
      }
    }
  `;
  document.head.appendChild(style);
  
  // 3秒后自动消失
  setTimeout(() => notification.remove(), 3000);
}

document.getElementById("getBtn").addEventListener("click", async () => {
  const output = document.getElementById("output");
  output.value = "处理中...";

  const tab = await getActiveTab();
  if (!tab?.url || !tab.url.startsWith("https://mp.weixin.qq.com/")) {
    output.value = "请先打开 mp.weixin.qq.com 页面";
    return;
  }

  const token = extractTokenFromUrl(tab.url);
  if (!token) {
    output.value = "未在URL中找到 token，请先点击后台任意菜单（如图文消息）";
    return;
  }

  const cookiesMp = await getCookies("mp.weixin.qq.com");
  const cookiesQq = await getCookies(".qq.com");
  const allCookies = [...cookiesMp, ...cookiesQq];

  const cookieStr = toCookieString(allCookies);
  const result = `Token: ${token}\n\nCookies: ${cookieStr}`;

  output.value = result;
  
  try {
    await navigator.clipboard.writeText(result);
    showSuccessNotification();
  } catch (err) {
    alert("复制失败: " + err.message);
  }
});
