# Releasing

**Tiếng Việt** | **English**

---

## 🇻🇳 Tiếng Việt

Cách phát hành một bản release lên PyPI. Việc phát hành sử dụng GitHub Actions
[Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC) — không có
API token nào được lưu trong repo. Workflow là
[`.github/workflows/release.yml`](../.github/workflows/release.yml).

### Thiết lập một lần (trước lần phát hành đầu tiên)

Làm bước này một lần. Cần tài khoản PyPI sẽ sở hữu dự án.

1. **PyPI pending publisher** — trên [pypi.org](https://pypi.org) → tài khoản của bạn →
   *Publishing* → *Add a pending publisher*:
   - PyPI Project Name: `hermes-inbox-organizer`
   - Owner: `hitechcloudvn`
   - Repository: `hermes-inbox-organizer`
   - Workflow: `release.yml`
   - Environment: `pypi`
2. **TestPyPI pending publisher** — lặp lại tương tự trên
   [test.pypi.org](https://test.pypi.org) với environment `testpypi`.
3. **GitHub environments** — repo → Settings → Environments → tạo `pypi` và
   `testpypi`. Tùy chọn: thêm mình làm người duyệt bắt buộc trên `pypi` để mỗi lần
   phát hành production đều cần một cú nhấp tay phê duyệt.

### Chạy thử trên TestPyPI (khuyên nghị)

1. GitHub → Actions → **Release** → *Run workflow* → target = `testpypi`.
2. Khi run chuyển xanh, xác nhận artifact cài được từ TestPyPI:
   ```sh
   pip install --index-url https://test.pypi.org/simple/ \
     --extra-index-url https://pypi.org/simple/ hermes-inbox-organizer
   ```
   (Extra index giúp các dependency được phân giải từ PyPI thật.)

### Phát hành một bản

1. Đảm bảo `main` đang xanh (CI: lint + tests trên 3.11–3.13) và build sạch ở
   local:
   ```sh
   uv build && uvx twine check --strict dist/*
   ```
2. Đặt phiên bản trong `pyproject.toml` (`project.version`). Release workflow
   **sẽ thất bại nếu git tag không khớp với điều này**, nên chúng phải trùng nhau.
3. Trong `CHANGELOG.md`, chuyển các mục ra khỏi `## [Unreleased]` vào một mục có
   ngày `## [X.Y.Z] - YYYY-MM-DD` và cập nhật các liên kết so sánh ở cuối.
4. Commit, sau đó tạo tag và đẩy tag:
   ```sh
   git commit -am "release: vX.Y.Z"
   git tag vX.Y.Z
   git push origin main vX.Y.Z
   ```
   Đẩy tag sẽ kích hoạt job build → publish-to-PyPI. (Nếu bạn đặt người duyệt trên
   environment `pypi`, hãy phê duyệt run trong tab Actions.)
5. Xác nhận bản đã lên sóng:
   ```sh
   pip install "hermes-inbox-organizer[live]==X.Y.Z"
   ```
6. Tạo một **GitHub Release** cho tag với phần changelog làm ghi chú:
   ```sh
   gh release create vX.Y.Z --title "vX.Y.Z" --notes-file <(sed -n '/## \[X.Y.Z\]/,/## \[/p' CHANGELOG.md)
   ```
   hoặc tạo từ giao diện Releases và dán phần changelog vào.

### Sau lần phát hành đầu tiên

- Tùy chọn: trỏ trang chủ repo tới trang PyPI:
  `gh repo edit --homepage https://pypi.org/project/hermes-inbox-organizer/`.
- Các pending publisher từ bước thiết lập sẽ tự động trở thành trusted publisher
  thông thường sau lần upload thành công đầu tiên.

---

## 🇬🇧 English

How to publish a release to PyPI. Publishing uses GitHub Actions
[Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC) — no API
token is ever stored in the repo. The workflow is
[`.github/workflows/release.yml`](../.github/workflows/release.yml).

### One-time setup (before the first publish)

Do this once. It needs the PyPI account that will own the project.

1. **PyPI pending publisher** — on [pypi.org](https://pypi.org) → your account →
   *Publishing* → *Add a pending publisher*:
   - PyPI Project Name: `hermes-inbox-organizer`
   - Owner: `hitechcloudvn`
   - Repository: `hermes-inbox-organizer`
   - Workflow: `release.yml`
   - Environment: `pypi`
2. **TestPyPI pending publisher** — repeat the same on
   [test.pypi.org](https://test.pypi.org) with environment `testpypi`.
3. **GitHub environments** — repo → Settings → Environments → create `pypi` and
   `testpypi`. Optionally add yourself as a required reviewer on `pypi` so every
   production publish needs a manual click.

### Dry run on TestPyPI (recommended)

1. GitHub → Actions → **Release** → *Run workflow* → target = `testpypi`.
2. When it's green, confirm the artifact installs from TestPyPI:
   ```sh
   pip install --index-url https://test.pypi.org/simple/ \
     --extra-index-url https://pypi.org/simple/ hermes-inbox-organizer
   ```
   (The extra index lets dependencies resolve from real PyPI.)

### Cut a release

1. Make sure `main` is green (CI: lint + tests on 3.11–3.13) and the build is
   clean locally:
   ```sh
   uv build && uvx twine check --strict dist/*
   ```
2. Set the version in `pyproject.toml` (`project.version`). The release workflow
   **fails if the git tag doesn't match this**, so they must agree.
3. In `CHANGELOG.md`, move items out of `## [Unreleased]` into a dated
   `## [X.Y.Z] - YYYY-MM-DD` section and update the compare links at the bottom.
4. Commit, then tag and push the tag:
   ```sh
   git commit -am "release: vX.Y.Z"
   git tag vX.Y.Z
   git push origin main vX.Y.Z
   ```
   Pushing the tag triggers the build → publish-to-PyPI job. (If you put a
   reviewer on the `pypi` environment, approve the run in the Actions tab.)
5. Confirm it's live:
   ```sh
   pip install "hermes-inbox-organizer[live]==X.Y.Z"
   ```
6. Cut a **GitHub Release** for the tag with the changelog section as the notes:
   ```sh
   gh release create vX.Y.Z --title "vX.Y.Z" --notes-file <(sed -n '/## \[X.Y.Z\]/,/## \[/p' CHANGELOG.md)
   ```
   or create it from the Releases UI and paste the changelog section.

### After the first publish

- Optionally point the repo homepage at the PyPI page:
  `gh repo edit --homepage https://pypi.org/project/hermes-inbox-organizer/`.
- The pending publishers from setup become regular trusted publishers
  automatically after the first successful upload.
