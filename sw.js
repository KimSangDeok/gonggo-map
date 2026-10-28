// 새 공고 알림(웹 푸시) 서비스 워커 — GitHub Actions(tools/notify_new.py)가 보낸 메시지를 이 기기 알림으로 띄움.
// 페이지·데이터 캐시는 하지 않음(지도는 늘 최신 data/*.json 을 읽음). 메시지 본문은 웹 푸시 표준(RFC 8291)으로 암호화돼 옴.
self.addEventListener('install', function(){ self.skipWaiting(); });
self.addEventListener('activate', function(e){ e.waitUntil(self.clients.claim()); });
self.addEventListener('push', function(e){
  var d = {};
  try { d = e.data ? e.data.json() : {}; } catch (err) { d = { title: '새 공고', body: e.data ? e.data.text() : '' }; }
  e.waitUntil(self.registration.showNotification(d.title || '새 공고', {
    body: d.body || '',
    icon: 'icon-192.png',
    badge: 'badge-96.png',
    data: { url: d.url || './', key: d.key || '' }
  }));
});
self.addEventListener('notificationclick', function(e){
  e.notification.close();
  var d = e.notification.data || {}, url = d.url || './';
  // 공고 키가 있으면 사이트를 거쳐 '확인'으로 표시한 뒤 공고로 넘어감(사이트 목록의 확인 체크)
  if (d.key) url = './#calendar&seen=' + encodeURIComponent(d.key) + '&go=' + encodeURIComponent(url);
  e.waitUntil(self.clients.openWindow(url));
});
