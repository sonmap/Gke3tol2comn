# 04. 1차 VM NFS 마운트 및 /mnt 경로 적용 절차

작성 목적: **실제 전환 대상 GKE Pod에서 Filestore NFS Mount 검증은 현재 수행할 수 없음.** 1차 인프라 단계에서는 **VM에서 기존 NFS 경로가 보이는지 확인하고**, 필요한 경우 NFS를 VM의 \`/mnt/batch_gke\`에 마운트하여 경로·접근권한만 검증한다.

> 주의: VM NFS 마운트 성공은 **GKE Autopilot Pod의 NFS 연결 성공 증거가 아닙니다**. 기존 [GKE/Filestore 설정 및 방화벽 계획](01-GKE-CLUSTER.md)은 **변경하지 않고 유지**합니다. GKE Node/Pod의 방화벽·PV/PVC 및 실제 Pod 마운트는 2차 시스템 연동 테스트 때 점검합니다.

## 1. 경로 매핑

| 대상 | 경로/역할 |
|---|---|
| NFS 서버 | \`NFS_SERVER\` — **서버 IP 미확정**, 실제 NFS/Filestore 담당자로부터 확인 |
| NFS export 루트 후보 | \`/batch_gke\` — 실제 \`showmount\`/NFSv4 Export 정책으로 확인 |
| VM NFS 마운트 지점 | \`/mnt/batch_gke\` |
| VM RSVP 과제 경로 | \`/mnt/batch_gke/l2/rsvp\` |
| VM SA JSON 키 *존재 여부만* 검사 | \`/mnt/batch_gke/l2/rsvp/.oefj\` |
| VM RSVP Python | \`/mnt/batch_gke/l2/rsvp/GP_L2RSVP_001_1/python\` |
| VM RSVP 런처 | \`/mnt/batch_gke/l2_gke_sh/rsvp/GP_L2RSVP_001_1/run-gke.sh\` — export 안에 실제 있는지 확인 |
| 미래 GKE Pod NFS Path | \`/batch_gke/l2/rsvp\` (PV 정의 후보) |
| 미래 GKE Pod Volume Mount | \`/home/jupyter\` — **1차에는 실행·검증하지 않음** |

**중요한 구분:** VM의 \`/mnt/batch_gke/l2/rsvp/.oefj\`와 Pod의 \`/home/jupyter/.oefj\`는 **서버 export 및 마운트 하위 경로가 일치할 경우에만** 동일한 파일입니다. Pod 경로가 보인다고 가정하지 마십시오.

또한 첨부 외부 개발환경 로그에서 \`MGMT_VM_IP=172.32.10.2\`와 \`NFS_SERVER=172.32.10.2\`가 겹칩니다. 해당 IP가 **관리 VM인지 NFS 서버인지 명확히 확인**해야 하며, 기존 다른 자료의 NFS 서버 주소를 검증 없이 대체하면 안 됩니다.

## 2. 기존 VM NFS 마운트 상태 조사 — 무변경/읽기 전용

실제 관리 VM에 접속하여 아래를 수행합니다. GCP API 호출이나 Pod 생성 없이 VM의 NFS/경로 상태만 확인합니다.

~~~bash
# 사용 중인 Linux 계정·OS 환경
whoami
id
hostname -f
ls -ld /mnt /mnt/batch_gke 2>&1 || true

# 현재 NFS 마운트 목록과 실제 Export 확인
findmnt -t nfs,nfs4 -o TARGET,SOURCE,FSTYPE,OPTIONS
findmnt -T /mnt/batch_gke -o TARGET,SOURCE,FSTYPE,OPTIONS || true
mountpoint /mnt/batch_gke && echo "EXISTING_MOUNTPOINT" || true
grep -nE '[[:space:]]/mnt/batch_gke[[:space:]]' /etc/fstab || true

# 이미 기존 VM에 마운트되어 있다면, 위치와 이름만 확인
ls -ld /mnt/batch_gke/l2/rsvp 2>&1 || true
ls -ld /mnt/batch_gke/l2/rsvp/GP_L2RSVP_001_1/python 2>&1 || true
ls -l /mnt/batch_gke/l2_gke_sh/rsvp/GP_L2RSVP_001_1/run-gke.sh 2>&1 || true

# 키 내용은 조회하지 않고 파일 존재/권한만 확인
if test -f /mnt/batch_gke/l2/rsvp/.oefj; then
  stat -c 'key_present mode=%a owner=%U:%G path=%n' \
    /mnt/batch_gke/l2/rsvp/.oefj
else
  echo "KEY_NOT_FOUND_OR_NFS_NOT_MOUNTED"
fi
~~~

- \`findmnt\`가 NFS 타입으로 \`/mnt/batch_gke\` 마운트를 표시하면 **그대로 재사용**, 중복 \`mount\` 명령 불필요.
- \`findmnt -T\`는 부모 파일시스템을 반환할 수도 있습니다. **\`mountpoint\` 및 SOURCE/FSTYPE도 함께 확인**해 실제 NFS인지 판정합니다.
- 디렉터리가 있다고 실제 NFS 마운트된 것은 아닙니다. \`ls\` 성공만으로 검증 완료 처리하지 않습니다.
- 기존 \`/mnt/batch_gke\`에 일반 로컬 파일이 있으면 새 마운트 시 해당 파일들이 가려질 수 있으므로 **강제로 마운트하지 않습니다**.

## 3. 신규 NFS 연결이 필요한 VM — 임시 경로로 안전하게 검증

**운영 담당자 승인 후** 수행합니다. 실 NFS 서버 IP, Export, 버전(NFSv3/v4.1)과 VM→NFS 방화벽이 확인되어야 합니다. VM에서 NFS를 설치·마운트하는 데는 OS 관리자 권한이 필요할 수 있습니다.

~~~bash
export NFS_SERVER="CONFIRM_REAL_NFS_SERVER_IP"
export NFS_EXPORT_ROOT="/batch_gke"
export VM_NFS_STAGE="/mnt/nfs-l2comm-stage"
export VM_NFS_ROOT="/mnt/batch_gke"

# 허위/예시 주소로 마운트 방지
case "$NFS_SERVER" in
  ""|"CONFIRM_REAL_NFS_SERVER_IP") echo "실제 NFS_SERVER 미확정"; exit 1 ;;
esac

# nfs-common (Ubuntu/Linux, 실제 설치 여부만 우선 확인)
command -v mount.nfs
command -v findmnt

# 네트워크 도달성만 점검 (연결 실패 원인 진단 시 사용)
nc -vz -w 5 "$NFS_SERVER" 2049
# showmount는 NFSv3에서 유용하며 NFSv4 전용 서버에서는 실패할 수 있음
showmount -e "$NFS_SERVER" || true

# 신규 설치 대상 파일을 가리지 않도록 별도 임시 디렉터리 사용
sudo mkdir -p "$VM_NFS_STAGE"
mountpoint -q "$VM_NFS_STAGE" && { echo "이미 마운트된 임시 경로"; exit 1; }

# read-only 검증. 실제 서비스가 NFSv3 전용이면 관리자 확인 후 vers=3으로 변경
sudo mount -t nfs -o ro,vers=4.1 \
  "$NFS_SERVER:$NFS_EXPORT_ROOT" "$VM_NFS_STAGE"

findmnt "$VM_NFS_STAGE" -o TARGET,SOURCE,FSTYPE,OPTIONS
ls -ld "$VM_NFS_STAGE/l2/rsvp"
test -d "$VM_NFS_STAGE/l2/rsvp/GP_L2RSVP_001_1/python"
test -f "$VM_NFS_STAGE/l2/rsvp/.oefj" \
  && echo "RSVP_SA_KEY_PRESENT" || echo "RSVP_SA_KEY_NOT_PRESENT"
test -f "$VM_NFS_STAGE/l2_gke_sh/rsvp/GP_L2RSVP_001_1/run-gke.sh" \
  && echo "RUN_GKE_PRESENT" || echo "RUN_GKE_NOT_IN_THIS_EXPORT"

# 임시 검사 완료 후 마운트 해제
sudo umount "$VM_NFS_STAGE"
~~~

**상태 판정:** NFSv4.1과 NFSv3은 사용하는 포트·Export 방식이 다를 수 있으므로 실패하면 \`vers=3\`을 임의 반복 적용하기보다 서버 설정 및 허용 포트 확인. \`Permission denied\`는 서버 허용 네트워크·권한, \`Connection timed out\`은 라우팅/FW, \`access denied by server\`는 NFS Export/클라이언트 접근을 각각 점검합니다.

## 4. VM 실제 /mnt/batch_gke 적용 — 승인 후 별도 단계

**이미 \`/mnt/batch_gke\`가 NFS로 마운트되어 있다면 아래 신규 마운트는 수행하지 않습니다.** 3번 임시 검증이 끝나고 실제 Export 경로가 옳다고 확인되었으며, 기존 로컬 파일/기존 마운트가 없는 경우에만 적용합니다.

~~~bash
export NFS_SERVER="CONFIRM_REAL_NFS_SERVER_IP"
export NFS_EXPORT_ROOT="/batch_gke"
export VM_NFS_ROOT="/mnt/batch_gke"

# NFS 서버 IP 확정 확인
test "$NFS_SERVER" != "CONFIRM_REAL_NFS_SERVER_IP" || exit 1

if mountpoint -q "$VM_NFS_ROOT"; then
  echo "기존 마운트 유지 — 중복 마운트하지 않음"
  findmnt "$VM_NFS_ROOT"
else
  # /mnt/batch_gke 경로에 로컬 데이터가 있는지 우선 확인할 것
  if [ -d "$VM_NFS_ROOT" ] && [ -n "$(ls -A "$VM_NFS_ROOT")" ]; then
    echo "로컬 디렉터리 비어 있지 않음: 기존 파일 확인 후 작업 중단"
    exit 1
  fi
  sudo mkdir -p "$VM_NFS_ROOT"
  sudo mount -t nfs -o ro,vers=4.1 \
    "$NFS_SERVER:$NFS_EXPORT_ROOT" "$VM_NFS_ROOT"
fi

findmnt "$VM_NFS_ROOT" -o TARGET,SOURCE,FSTYPE,OPTIONS
ls -ld "$VM_NFS_ROOT/l2/rsvp"
~~~

1차의 기본 mount는 **읽기 전용(ro)**이며, 이 상태에서는 NFS 소스 및 키 파일을 수정하지 않습니다. VM 배치가 실제로 쓰기 권한을 필요로 한다면 NFS Export 서버측 권한, 파일 소유권, 분리된 작업 경로를 담당자가 검토한 뒤 **별도 승인 후 rw로 변경**합니다. Git 저장소에 키 파일을 업로드하거나 권한을 무조건 777로 변경하지 않습니다.

운영 재부팅 후 자동 마운트가 꼭 필요한 경우 승인된 서버값으로만 \`/etc/fstab\`에 아래 형식의 항목을 별도 변경관리로 추가합니다 (예시):

~~~fstab
# 예시만: NFS_SERVER 실제 IP로 변경 후 승인 필요. 이미 등록돼 있으면 중복 추가 금지.
<NFS_SERVER>:/batch_gke /mnt/batch_gke nfs ro,vers=4.1,_netdev,nofail,x-systemd.automount 0 0
~~~

\`fstab\` 적용 전에 \`findmnt\` / \`systemctl\` / NFS 서버 네트워크 선행 조건과 마운트 정책을 검증합니다. 이번 GitHub 수정으로 VM의 \`/etc/fstab\`이 자동 변경되는 것은 아닙니다.

## 5. VM 검증 완료 시 수집할 증적

| 확인 | 명령/확인 결과 | 판정 |
|---|---|---|
| VM NFS 마운트 | \`findmnt /mnt/batch_gke\` | NFS/NFS4 SOURCE와 Mountpoint 확인 |
| RSVP 디렉터리 | \`ls -ld /mnt/batch_gke/l2/rsvp\` | 경로 존재/조회 |
| Python 업무 경로 | \`ls -ld /mnt/batch_gke/l2/rsvp/GP_L2RSVP_001_1/python\` | 경로 존재 |
| 실행기 | \`ls -l /mnt/batch_gke/l2_gke_sh/rsvp/GP_L2RSVP_001_1/run-gke.sh\` | 존재 또는 다른 Export/위치 기록 |
| 서비스 계정 키 | \`stat\`으로 .oefj 존재/권한만 기록 | 키 내용 비공개 |
| NFS 접근 제어 | VM 소스 IP·대상 Export, NFS 버전 | VM 기준 접근성 설명 |
| 미검증 | GKE Pod NFS Mount/PV/PVC | 2차 검증 보류 |

## 6. 포인트: VM 검증 ≠ Pod 검증

- VM→NFS 성공 시 **VM 마운트·경로 접근 가능**이라는 사실만 확인.
- GKE Node/Pod의 네트워크 소스는 VM IP와 다르므로 Filestore Export 허용 대역 및 VPC FW 규칙은 기존 문서대로 유지하며 2차 때 재검증.
- Pod VolumeMount \`/home/jupyter\` 및 PV \`/batch_gke/l2/rsvp\` 설정은 기존 테스트 구조를 유지하지만 **1차에 Pod를 띄우지 않음**.
- BigQuery 인증 .oefj는 기존 경로 기준 존재 여부만 확인하며, **1차에 BigQuery API 호출하지 않음**.
- \`run-gke.sh\`, \`client_gke\` 링크, Cron은 기존대로 유지.

참고 문서: [00 1차 인프라 설치계획](00-PHASE1-INFRA-INSTALL.md) / [01 GKE/Filestore 구성](01-GKE-CLUSTER.md) / [02 후속 RSVP 검증](02-RSVP-CUTOVER.md).
