# workspace — Claude 사용량 자동 수집

깃허브 서버가 하루 4회(한국 시간 08:07, 12:07, 17:07, 22:07) Claude Code를 한 번 짧게 실행하고,
그때 함께 나오는 구독 사용률을 `data/` 폴더에 쌓습니다. PC가 꺼져 있어도 동작합니다.
주간 한도 리셋(월요일 06:00) 직전인 월요일 05:17에도 한 번 더 읽어 그 주의 최종 사용률을 남깁니다.

## 쌓이는 데이터

| 파일 | 내용 |
|---|---|
| `data/usage.json` | 수집할 때마다 한 건: 시각, 5시간 사용률, 주간 사용률, 각 리셋 시각 |
| `data/weekly.json` | 주 단위 집계: 그 주의 최고 사용률(= 그 주 사용량), 기록 횟수 |

## 설정 순서

### 1. PC에서 확인 (최초 1회)

PowerShell을 열고 차례로 실행합니다.

```powershell
claude --version
```

"찾을 수 없다"고 나오면 먼저 설치합니다.

```powershell
irm https://claude.ai/install.ps1 | iex
```

설치 후 `claude` 를 실행해 Claude 계정으로 로그인한 다음, 아래 확인 명령을 실행합니다.

```powershell
claude -p "Reply with the single word: done" --model haiku --output-format stream-json --verbose | Select-String "rate_limit_event"
```

출력된 줄에 `unifiedWindows` 와 `seven_day` 가 보이면 이 방식으로 수집할 수 있습니다.
보이지 않으면 여기서 멈추고 다른 방법을 찾아야 합니다.

### 2. 장기 토큰 발급 (최초 1회, 약 1년 유효)

```powershell
claude setup-token
```

브라우저에서 승인하면 `sk-ant-` 로 시작하는 토큰이 나옵니다. 이 값은 비밀번호와 같으니
채팅이나 파일에 붙여 넣지 말고 다음 단계의 깃허브 비밀값 칸에만 넣습니다.

### 3. 깃허브 저장소 설정

1. 이 폴더의 파일들이 올라간 저장소에서 **Settings → Secrets and variables → Actions → New repository secret**
2. Name: `CLAUDE_CODE_OAUTH_TOKEN`, Secret: 2단계의 토큰
3. **Actions** 탭 → "Claude 사용량 수집" → **Run workflow** 로 첫 실행
4. 성공하면 `data/usage.json` 에 첫 기록이 생깁니다. 이후는 자동입니다.

## 알아둘 점

- 수집 한 번마다 아주 짧은 호출이 실제로 나가므로 사용량이 조금 들고, 그 시점에 5시간 세션이 시작될 수 있습니다.
- 수집되는 값은 5시간과 주간 전체 두 가지입니다. Fable 주간 한도는 이 경로로 나오지 않습니다.
- 사용률이 출력에 실리는 것은 공식 문서에 명시된 기능이 아니어서, Claude Code 버전이 바뀌면 중단될 수 있습니다.
  그 경우 Actions 실행이 "실패"로 표시됩니다.
- 수집 주기를 바꾸려면 `.github/workflows/collect-usage.yml` 의 `cron` 줄을 고칩니다(UTC 기준).
- 토큰이 만료되거나 유출이 의심되면 `claude setup-token` 을 다시 실행해 새 값으로 비밀값을 교체합니다.
