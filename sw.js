// 새 공고 알림(웹 푸시) 서비스 워커 — GitHub Actions(tools/notify_new.py)가 보낸 메시지를 이 기기 알림으로 띄움.
// 페이지·데이터 캐시는 하지 않음(지도는 늘 최신 data/*.json 을 읽음). 메시지 본문은 웹 푸시 표준(RFC 8291)으로 암호화돼 옴.
// 알림 기록(2026-11-19 '니가 확인할 만한 로그는 전부 추가해'): 받음·누름·띄우기 실패·구독 만료·오류를 이 기기 Cache Storage 'kkk-swlog' 에 최근 30건 →
// 사이트를 열면 '오류 기록'으로 옮겨지고, 기기 동기화가 켜져 있으면 prefs 가지 log/ 로 올라가 Claude 가 봄. 알림 제목·본문은 안 적음(공고 키만)
function swlog(m, x){
  var e = { t: new Date().toISOString(), m: String(m).slice(0, 200), x: String(x || '').slice(0, 200) };
  return caches.open('kkk-swlog').then(function(c){
    return c.match('log').then(function(r){ return r ? r.json() : []; }).catch(function(){ return []; }).then(function(a){
      if (!Array.isArray(a)) a = []; a.push(e); if (a.length > 30) a = a.slice(-30);
      return c.put('log', new Response(JSON.stringify(a), { headers: { 'content-type': 'application/json' } }));
    });
  }).catch(function(){});
}
self.addEventListener('install', function(){ self.skipWaiting(); });
self.addEventListener('activate', function(e){ e.waitUntil(self.clients.claim()); });
self.addEventListener('push', function(e){
  var d = {}, bad = false;
  try { d = e.data ? e.data.json() : {}; } catch (err) { bad = true; d = { title: '새 공고', body: e.data ? e.data.text() : '' }; }
  e.waitUntil(self.registration.showNotification(d.title || '새 공고', {
    body: d.body || '',
    icon: 'icon-192.png',
    badge: 'badge-96.png',
    data: { url: d.url || './', key: d.key || '' }
  }).then(function(){ return swlog('알림 받아 띄움' + (bad ? '(내용 해석 실패 — 글자 그대로 띄움)' : ''), d.key || ''); },
          function(err){ return swlog('알림 띄우기 실패', (err && err.message) || String(err)); }));
});
self.addEventListener('notificationclick', function(e){
  e.notification.close();
  var d = e.notification.data || {}, url = d.url || './';
  // 공고 키가 있으면 사이트 지도에서 그 공고 단지를 보여 주고 '확인'으로 표시(공고 원문은 사이트의 '공고문 ↗') — 2026-11-02부터
  if (d.key) url = './#map&seen=' + encodeURIComponent(d.key) + '&nt=' + encodeURIComponent(d.key);
  e.waitUntil(Promise.all([self.clients.openWindow(url), swlog('알림 누름', d.key || '')]));
});
// 브라우저가 푸시 구독을 바꾸거나 없앰 → 저장소 data/push/ 의 옛 구독으로는 더 안 옴(사이트에서 다시 구독·등록 필요)
self.addEventListener('pushsubscriptionchange', function(e){ e.waitUntil(swlog('푸시 구독이 바뀌거나 만료됨 — 사이트 "이 기기로 알림 받기"에서 다시 구독·등록 필요', '')); });
self.addEventListener('error', function(e){ swlog('서비스 워커 오류', (e && e.message) || ''); });
self.addEventListener('unhandledrejection', function(e){ var r = e && e.reason; swlog('서비스 워커 오류(비동기)', (r && r.message) || String(r)); });
