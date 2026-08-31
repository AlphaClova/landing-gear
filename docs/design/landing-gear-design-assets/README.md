# Landing Gear 디자인 자산

선택한 시작 화면과 홈 화면 디자인을 실제 프론트엔드에 적용하기 위한 자산입니다.

## 권장 위치

압축을 푼 뒤 `assets/` 내부 파일을 아래 위치로 복사합니다.

```text
frontend/public/assets/
├─ brand/
│  ├─ landing-gear-logo.svg
│  └─ landing-gear-mark.svg
├─ backgrounds/
│  ├─ start-landing-path.svg
│  └─ home-horizon.svg
└─ icons/
   ├─ pension-chat.svg
   ├─ withdrawal-decision.svg
   ├─ exact-estimate.svg
   ├─ evidence.svg
   └─ condition.svg
```

`reference/landing-gear-design-reference.png`는 Codex에 첨부할 디자인 기준 화면입니다. 실제 웹에 포함하지 않아도 됩니다.

## 서체

- 일반 UI: Pretendard Variable
- `Landing Gear` 로고: Cormorant Garamond 600

로고 SVG는 `Cormorant Garamond → Georgia → serif` 순서로 대체됩니다. 디자인을 동일하게 유지하려면 웹폰트를 먼저 불러옵니다.

```css
@import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.css");
@import url("https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600&display=swap");

:root {
  font-family: "Pretendard Variable", Pretendard, sans-serif;
}
```

## 사용 예시

```tsx
<img src="/assets/brand/landing-gear-logo.svg" alt="Landing Gear" />
```

```css
.start-page {
  background: #f7f2ea url("/assets/backgrounds/start-landing-path.svg") center / cover no-repeat;
}

.home-hero::after {
  content: "";
  position: absolute;
  inset: 0 0 auto auto;
  width: min(60%, 1000px);
  height: 360px;
  background: url("/assets/backgrounds/home-horizon.svg") right top / contain no-repeat;
  pointer-events: none;
}
```

## 적용 원칙

- 시작 화면 배경에는 `start-landing-path.svg`만 사용합니다.
- 홈 상단 장식에는 더 옅은 `home-horizon.svg`를 사용합니다.
- 아이콘은 카드나 답변 원칙 영역에만 사용하고 한 화면에 반복해서 남용하지 않습니다.
- 메뉴 아이콘은 이미지 자산보다 Lucide React의 선형 아이콘 사용을 권장합니다.
- 팀명, 공모전명, 기술명은 사용자 화면에 노출하지 않습니다.
- 아이보리·네이비·골드 색상 체계를 다른 화면에서도 유지합니다.

## 기준 색상

```css
--navy-950: #061b38;
--navy-900: #0a274d;
--navy-800: #12365f;
--ivory-50: #faf7f1;
--ivory-100: #f4eee5;
--stone-200: #e6ddd0;
--stone-500: #82796f;
--gold-500: #c99a4b;
--gold-300: #e3c58c;
--text-primary: #102542;
--text-secondary: #625f5a;
```
