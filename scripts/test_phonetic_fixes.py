import urllib.request
import json
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

test_cases = [
    # 3 trường hợp người dùng gặp lỗi trong ảnh
    ("bài nàng thuốc", "music", "Bài Nàng Thơ"),
    ("bật mô bài nhà", "music", "Bật một bài nhạc"),
    ("bật bài hấp của xuân tùng", "music", "Bật bài hát của Sơn Tùng"),
    
    # Các trường hợp biến thể sai chính tả khác
    ("bật bài hát của sơn tùng", "music", "Bật bài hát của Sơn Tùng (có từ 'của')"),
    ("bật bài", "music", "Bật bài chung"),
    ("bài sóng gió", "music", "Bài Sóng Gió"),
    ("mô bài nhạc hot", "music", "Mô bài nhạc hot"),
    
    # Lệnh thiết bị sai chính tả âm vị
    ("bực đèng phòng khách", "light_on", "Bực đèng -> Bật đèn"),
    ("tắt đèng phòng khách", "light_off", "Tắt đèng -> Tắt đèn"),
    ("bật quạc phòng khách", "fan_on", "Bật quạc -> Bật quạt"),
    ("tắt quạc phòng khách", "fan_off", "Tắt quạc -> Tắt quạt"),
    
    # Lệnh an ninh cửa (Phải từ chối mở cửa thật sự)
    ("mở cửa chính", "security_refuse", "Mở cửa -> Từ chối"),
    ("khóa cửa chính", "lock", "Khóa cửa an toàn")
]

url = "http://localhost:8093/xiaozhi/test_text"

print("=" * 60)
print("TESTING VIETNAMESE PHONETIC & TYPO TOLERANCE ENGINE")
print("=" * 60)

passed = 0
for text, category, note in test_cases:
    payload = json.dumps({"text": text, "room": "living"}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25.0) as res:
            res_json = json.loads(res.read().decode("utf-8"))
            reply = res_json.get("reply_text", "")
            emotion = res_json.get("emotion", "")
            dev_id = res_json.get("device_id", "")
            act = res_json.get("action", "")
            
            # Validation logic
            ok = False
            if category == "music":
                # Không được là câu từ chối mở cửa
                # Phải là phát nhạc (emotion music hoặc reply có 'phát bài' / 'loa' / 'nhạc')
                if "an ninh" not in reply.lower() and ("phát" in reply.lower() or "bài hát" in reply.lower() or "loa" in reply.lower() or emotion == "music"):
                    ok = True
            elif category == "light_on":
                if dev_id == "living-light" and act == "on":
                    ok = True
            elif category == "light_off":
                if dev_id == "living-light" and act == "off":
                    ok = True
            elif category == "fan_on":
                if dev_id == "living-fan" and act == "on":
                    ok = True
            elif category == "fan_off":
                if dev_id == "living-fan" and act == "off":
                    ok = True
            elif category == "security_refuse":
                if "an ninh" in reply.lower() and "không thể mở cửa" in reply.lower():
                    ok = True
            elif category == "lock":
                if dev_id == "entry-lock" and act == "lock":
                    ok = True
            
            status_icon = "✅ PASS" if ok else "❌ FAIL"
            if ok:
                passed += 1
            print(f"{status_icon} [{note}]")
            print(f"   Input:   '{text}'")
            print(f"   Output:  '{reply}' (Emotion: {emotion}, Dev: {dev_id}, Act: {act})")
            print("-" * 60)
    except Exception as e:
        print(f"❌ ERROR [{note}] '{text}': {e}")
        print("-" * 60)

print(f"KẾT QUẢ ĐÁNH GIÁ: {passed}/{len(test_cases)} ({passed/len(test_cases)*100:.1f}%)")
