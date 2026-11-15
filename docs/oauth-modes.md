# OAuth Modes — Testing vs Production Audience

**Tiếng Việt** | **English**

---

## 🇻🇳 Tiếng Việt

Đây là lỗi thường gặp nhất đối với người tự vận hành: **app audience** (đối tượng ứng dụng) OAuth của Google quyết định refresh token sống được bao lâu.

---

### Chế độ Testing (mặc định sau khi tạo consent screen lần đầu)

Khi OAuth consent screen của bạn ở chế độ **Testing**:

- Refresh token hết hạn sau **7 ngày**.
- Chỉ những test user bạn liệt kê rõ ràng mới có thể cấp quyền truy cập.
- Ổn cho thiết lập ban đầu và dùng thử — sẽ "chết" sau một tuần trừ khi người dùng đồng ý lại (re-consent).

**Triệu chứng:** Đồng bộ Gmail dừng lại với lỗi "Token has been expired or revoked" khoảng bảy ngày sau khi kết nối OAuth.

---

### Production audience — ứng dụng chưa xác minh

Đưa ứng dụng lên **Production** audience sẽ loại bỏ thời hạn 7 ngày, ngay cả khi chưa được Google xác minh:

- Refresh token sống lâu (chỉ bị thu hồi khi ngắt kết nối rõ ràng hoặc khi có sự kiện bảo mật từ Google).
- Bất kỳ tài khoản Google nào cũng có thể cấp quyền truy cập, không chỉ test user.
- Google hiển thị màn hình cảnh báo đáng sợ "This app isn't verified" cho người dùng không phải test user — điều này là bình thường và chấp nhận được với việc tự triển khai cho một người vận hành.

**Đây là chế độ phù hợp cho các bản triển khai tự host cá nhân hoặc nhóm nhỏ.**

#### Cách đưa lên Production

1. Mở [Google Cloud Console](https://console.cloud.google.com/) và chọn project của bạn.
2. Đi tới **APIs & Services → OAuth consent screen**.
3. Cuộn xuống phần **Publishing status**.
4. Nhấp **Publish App**.
5. Xác nhận cảnh báo — Google sẽ hỏi bạn có muốn tiếp tục mà không cần xác minh hay không.
6. Sau khi xuất bản, mọi lần cấp quyền OAuth mới đều tạo ra refresh token sống lâu.

Các token ngắn hạn hiện có từ chế độ Testing sẽ không tự động được nâng cấp. Hãy cho từng tài khoản kết nối lại qua `/oauth/connect` để nhận một token mới sống lâu.

---

### Production audience — ứng dụng đã xác minh

Việc xác minh loại bỏ cảnh báo "unverified" và là bắt buộc nếu:

- Bạn phân phối cho người dùng ngoài tổ chức của mình, **và**
- Bạn muốn một consent screen sạch sẽ, không có màn hình cảnh báo đáng sợ.

Việc xác minh yêu cầu đánh giá bảo mật của Google đối với các scope nhạy cảm như `gmail.modify`. Điều này nằm ngoài phạm vi của các bản triển khai tự host V1.

---

### Tóm tắt

| Chế độ | Thời hạn refresh token | Dùng cho |
|---|---|---|
| Testing | 7 ngày | Chỉ phát triển ban đầu |
| Production (unverified) | Sống lâu | Tự host, dùng cá nhân |
| Production (verified) | Sống lâu | Phân phối rộng, không cảnh báo |

Với thiết lập tự host cho một người vận hành: hãy đưa lên Production (unverified) và chấp nhận màn hình cảnh báo một lần.

---

## 🇬🇧 English

This is the single most common gotcha for self-hosted operators: Google's OAuth **app audience** controls how long refresh tokens last.

---

### Testing mode (default after first consent-screen creation)

When your OAuth consent screen is in **Testing** mode:

- Refresh tokens expire after **7 days**.
- Only test users you explicitly list can grant access.
- Fine for initial setup and kicking the tires — dies after a week unless the user re-consents.

**Symptom:** Gmail sync stops with a "Token has been expired or revoked" error roughly seven days after OAuth connect.

---

### Production audience — unverified app

Publishing your app to **Production** audience removes the 7-day expiry, even without Google verification:

- Refresh tokens are long-lived (revoked only on explicit disconnect or Google security event).
- Any Google account can grant access, not just test users.
- Google shows a scary "This app isn't verified" interstitial to non-test users — that is expected and acceptable for single-operator, self-hosted use.

**This is the right mode for personal or small-team self-hosted deployments.**

#### How to publish to Production

1. Open [Google Cloud Console](https://console.cloud.google.com/) and select your project.
2. Navigate to **APIs & Services → OAuth consent screen**.
3. Scroll to the **Publishing status** section.
4. Click **Publish App**.
5. Confirm the warning — Google will ask if you want to proceed without verification.
6. After publishing, any new OAuth grant will produce a long-lived refresh token.

Existing short-lived tokens from Testing mode are not automatically upgraded. Have each account re-connect via `/oauth/connect` to get a fresh long-lived token.

---

### Production audience — verified app

Verification removes the "unverified" warning and is required if:

- You are distributing to users outside your organization, **and**
- You want a clean consent screen without the scary interstitial.

Verification requires a Google security assessment for sensitive scopes like `gmail.modify`. This is out of scope for V1 self-hosted deployments.

---

### Summary

| Mode | Refresh token expiry | Required for |
|---|---|---|
| Testing | 7 days | Initial dev only |
| Production (unverified) | Long-lived | Self-hosted personal use |
| Production (verified) | Long-lived | Wide distribution, no warning |

For a single-operator self-hosted setup: publish to Production (unverified) and accept the one-time warning screen.
