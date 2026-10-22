# 02. RSVP 단일 과제 전환 검증 (GP_L2RSVP_001_1)

**목표:** 30개 배치 중 RSVP 1개만 GKE Autopilot에 실행. **기존 Cron·client_gke 공통 링크·GKE Standard는 변경하지 않는다.**

## 0. 사전 승인 및 검증 데이터

| 항목 | 설정/확인 |
|---|---|
| 과제 ID | GP_L2RSVP_001_1 |
| Cron/VM | 실제 VM/Linux 사용자 확인, GCP 실행 계정은 user01@sonmap.net |
| 실행 스크립트 | /mnt/batch_gke/l2_gke_sh/rsvp/GP_L2RSVP_001_1/run-gke.sh |
| 기존 실행 클라이언트 | /ssw/dlk/client_gke (Bash) |
| 신규 검증용 클라이언트 | /ssw/dlk/client-gke-auto (신규 복제/수정) |
| Kubeconfig | $HOME/.kube/config_l2comn-autopilot (첨부 로그 기준) |
| GKE Node/Pod/CP CIDR | 10.253.0.0/28 · 10.253.1.0/24 · 10.253.2.0/28 |
| Service Project | gcp-sbx-edp-comn-509423 |
| AR Project | gcp-prod-edp-hub-vpchost |
| 채널 | regular |
| 관리 VM | 172.32.10.2 (NFS 로그 값과 충돌) |
| GKE Namespace | l2comm-batch |
| KSA | ksa-l2comm-batch (존재 확인) |
| NFS Export | /batch_gke/l2/rsvp |
| Pod 마운트 | /home/jupyter |
| BQ SA Key | /home/jupyter/.oefj (NFS 상위 경로 파일이 매핑될 때) |
| Python | /home/jupyter/GP_L2RSVP_001_1/python/sample_bq.py |
| BQ 조회 | gcp-prod-edp-lake.DLKUDF.L2MQ_TL_SUBJ_H_TEST |
| 실행 로그상의 스모크 이미지 | asia-northeast3-docker.pkg.dev/gcp-prod-edp-hub-vpchost/ar-l2comm-python/python-bq-batch:v1 |
| 변수 정의의 또 다른 후보 | asia-northeast3-docker.pkg.dev/gcp-prod-edp-hub-vpchost/ar-l2comm-python/1a751e99d693:v1 (대조 필요) |

위 경로/이미지는 2026-10-22 첨부 운영 설정 및 예시 출력에서 유래함. 실제 클러스터를 새로 검증한 로그가 아니므로 재검증이 필요함. 실제 RSVP 업무 이미지(태그), 인자, Cron 스케줄은 현장 조회로 확정. 컨테이너가 sample_bq.py와 Python BigQuery 패키지를 실행할 수 있어야 함.

## 운영 입력값 간 충돌 (생성/실행 전에 검증)

- Node 10.253.0.0/28은 총 16개, GCP 예약 주소 4개를 제외하면 12개 사용 가능. 이전 주석의 128개는 오류.
- MGMT_VM_IP 및 실행 출력의 NFS_SERVER가 모두 172.32.10.2인 것은 의심스러움. Filestore 담당자의 서버 IP 확정 전에 배포하지 않음.
- TEST_IMAGE 변수는 1a751e99d693:v1, 출력은 python-bq-batch:v1. 실제 업무 이미지는 따로 확인해야 함.
- Kubeconfig 경로가 config_new-autopilot, config_l2comn-autopilot, l2comn_gke 등으로 혼재함. 실행 로그에 명시된 config_l2comn-autopilot을 이 문서의 기본값으로 사용.
- 신규 smoke 인증은 .oefj. 과거 일부 Python config.py는 .oef이므로 전체 업무 전환 전에는 별도 호환성 확인.

## 1. 실행 VM에서 원본 조사 (읽기 전용)

GKE 접근과 RSVP 1차 검증의 **실제 gcloud 실행 계정은 `user01@sonmap.net`**입니다. IAM 변경은 승인된 관리자 계정이 별도 수행하며, 테스트 중 `admin@sonmap.net`으로 바꾸어 실행하지 않습니다. 이전 실행 로그의 Linux 계정 경로는 역사적 증적이므로 유지합니다.

~~~bash
export EXEC_ACCOUNT="user01@sonmap.net"
gcloud auth list
gcloud config set account "$EXEC_ACCOUNT"
test "$(gcloud config get-value account 2>/dev/null)" = "$EXEC_ACCOUNT" || exit 1

export RUN_SCRIPT="/mnt/batch_gke/l2_gke_sh/rsvp/GP_L2RSVP_001_1/run-gke.sh"
export CLIENT_AUTO="/ssw/dlk/client-gke-auto"
export KUBECONFIG="$HOME/.kube/config_l2comn-autopilot"
export NS="l2comm-batch"

ls -l "$RUN_SCRIPT" /ssw/dlk/client_gke /ssw/dlk/client_common
readlink -f /ssw/dlk/client_gke
file /ssw/dlk/client_gke
head -n 3 /ssw/dlk/client_gke
grep -nE 'client[_-]gke|CLIENT_GKE|DOCKER_IMAGE|KUBECONFIG|dry.run|PROGRAM_ID' "$RUN_SCRIPT"
grep -nE 'KUBECONFIG|kubectl apply|serviceAccountName|nfs|volumeMounts' /ssw/dlk/client_gke
kubectl get sa -n "$NS"
kubectl auth can-i create pods -n "$NS"
kubectl auth can-i create persistentvolumes
kubectl auth can-i create persistentvolumeclaims -n "$NS"
~~~

**중요:** client_gke는 현재 확보된 자료상 Python(.py)이 아니라 Bash 스크립트임. YAML은 script 내부 here-document로 생성될 수 있음. 실제 소스와 런처가 본 저장소에 없으므로 호출 인자·옵션 지원 여부는 위 조회로 확인해야 함.

## 2. 신규 client-gke-auto 준비 — 공통 링크 변경 금지

~~~bash
# 현장 운영 담당자가 기존 동작 파일을 바탕으로 복제
cd /ssw/dlk
cp -p "$(readlink -f client_gke)" client-gke-auto
chmod 750 client-gke-auto

# 편집 대상은 오직 client-gke-auto
# KUBECONFIG=$HOME/.kube/config_l2comn-autopilot
# Namespace=l2comm-batch / KSA=ksa-l2comm-batch
# NFS mount, 이미지, CPU·MEM·GPU, Pod/PV/PVC명과 환경변수/인자 확인
# exit code / trap / 키 복사·삭제 로직도 점검
~~~

복제본에 적용할 Kubeconfig 기본 설정 **예시**:

~~~bash
export KUBECONFIG="$HOME/.kube/config_l2comn-autopilot"
~~~

- 사용자 요청 경로인 $HOME/.kube/config_l2comn-autopilot를 사용.
- 기존 소스에 고정된 kubeconfig, nms-prd, nms-prd-sa, NFS 경로는 신규 값으로 교체할지 판단.
- 코드에 .oef/.oefj 복사·삭제가 있으면 다른 배치와 키 충돌이 없는지 점검. **키 원본 삭제 금지**.
- 기존 클러스터 실행 파일을 직접 덮어쓰지 않음.
- 이미 실행 중인 Cron과 같은 결과 테이블을 동시에 갱신하지 않도록 제한.

## 3. 1차 샘플 Pod 단위 테스트

[01. GKE 생성 가이드](01-GKE-CLUSTER.md) 완료 후 수행.

테스트 전 NFS 경로에 본 저장소 tests/sample_bq.py를 배포:

~~~bash
# 실제 NFS를 쓰기 가능한 관리 VM에서만 실행
install -m 0644 tests/sample_bq.py \
  /mnt/batch_gke/l2/rsvp/GP_L2RSVP_001_1/python/sample_bq.py

test -s /mnt/batch_gke/l2/rsvp/.oefj
# 키 파일 내용/비밀키는 절대 cat, 로그, Git 업로드 금지
~~~

샘플 YAML은 [rsvp-smoke.yaml.template](../tests/rsvp-smoke.yaml.template) 사용.
Filestore 주소와 테스트 이미지 정보를 승인 후 환경변수로 대입:

~~~bash
export FILESTORE_IP="CONFIRM_REAL_FILESTORE_IP"
export NFS_EXPORT="/batch_gke/l2/rsvp"
export TEST_IMAGE="asia-northeast3-docker.pkg.dev/gcp-prod-edp-hub-vpchost/ar-l2comm-python/python-bq-batch:v1"
export KUBECONFIG="$HOME/.kube/config_l2comn-autopilot"

# 운영 담당자가 실제 NFS 서버를 검증한 후에만 표시. 주소가 관리 VM과 같아도
# 해당 VM에서 NFS를 실제로 제공하는지 확인되면 승인 가능.
export NFS_IP_VERIFIED="no"
# 네트워크/스토리지 담당 확인 후 위 값을 yes로 변경
test "$NFS_IP_VERIFIED" = "yes" || { echo 'NFS IP 미확정: 배포 중단'; exit 1; }
test "$FILESTORE_IP" != "CONFIRM_REAL_FILESTORE_IP" || exit 1
envsubst < tests/rsvp-smoke.yaml.template > /tmp/rsvp-smoke.yaml
kubectl apply --dry-run=server -f /tmp/rsvp-smoke.yaml
# 검토 및 승인 후에만:
kubectl apply -f /tmp/rsvp-smoke.yaml
kubectl get pods -n l2comm-batch -w
kubectl logs -n l2comm-batch rsvp-bq-smoke --timestamps
kubectl get pod rsvp-bq-smoke -n l2comm-batch \
  -o jsonpath='{.status.phase}{"\n"}{.status.containerStatuses[0].state.terminated.exitCode}{"\n"}'
~~~

성공: Image Pull → PV/PVC Bound → NFS Mount → .oefj 인증 → BigQuery SELECT → Pod Succeeded 및 컨테이너 종료코드 0.

증적 확보 후 정리 (테스트 이름만 삭제):

~~~bash
kubectl describe pod rsvp-bq-smoke -n l2comm-batch > /tmp/rsvp-bq-smoke-describe.txt
kubectl logs rsvp-bq-smoke -n l2comm-batch > /tmp/rsvp-bq-smoke-log.txt
kubectl delete pod rsvp-bq-smoke -n l2comm-batch --wait=true
kubectl delete pvc pvc-rsvp-bq-smoke -n l2comm-batch
kubectl delete pv pv-rsvp-bq-smoke
~~~

## 4. RSVP run-gke.sh → client-gke-auto 연결 테스트

현재 실제 쉘 소스가 저장소에 없어 다음 두 방식 중 **실제 쉘 소스 확인 후 하나 선택**:

### A. run-gke.sh가 CLIENT_GKE 환경변수를 지원하는 경우

~~~bash
grep -n 'CLIENT_GKE' "$RUN_SCRIPT"
export CLIENT_GKE=/ssw/dlk/client-gke-auto
export GKE_KUBECONFIG="$HOME/.kube/config_l2comn-autopilot"

# 아래는 과거 테스트 이력의 인자 구조 예시.
# 실제 인자 순서 및 --dry-run 지원 여부 확인 후 실행.
# DRY_RUN=1 bash "$RUN_SCRIPT" --dry-run \
#   YYYYMMDD YYYYMMDD YYYYMMDD HHMMSS 0 4 16 \
#   /home/jupyter/GP_L2RSVP_001_1/python python sample_bq.py
~~~

### B. run-gke.sh가 고정된 /ssw/dlk/client_gke만 호출하는 경우

- 운영 원본 run-gke.sh를 보존하고 같은 디렉터리에 별도 run-gke-rsvp-test.sh 복제.
- **복제본의 실행기 호출 경로만** /ssw/dlk/client-gke-auto로 변경.
- 나머지 인자와 업무 이미지 태그는 기존과 동일하게 유지.
- DRY_RUN은 생성되는 Pod/PV/PVC YAML과 클러스터 컨텍스트 리뷰.
- 실 실행은 중복 실행/DB 변경에 대해 업무 담당 승인 후 수행.

**주의:** 기존 run-gke.sh가 지원하지 않는 --dry-run이나 CLIENT_GKE 인자를 억지로 적용하지 말 것.

## 5. 실제 RSVP 업무 전환 판정

| 검증 | 확인 | Go 기준 |
|---|---|---|
| 기존 | Cron 및 run-gke 원본 보존 | 변경 없음 |
| 접속 | 신규 Kubeconfig | Autopilot context |
| 이미지 | 업무용 Tag | Pull 성공 |
| Filestore | Pod /home/jupyter | mount 및 소스 파일 접근 |
| BQ | SA .oefj | SELECT 실행 및 정상 종료 |
| Pod | phase + exitCode | Succeeded + 0 |
| 업무 | 기간/결과/건수/로그 | 업무 담당 승인 |
| 데이터 | 중복 적재·변경 | 없음 |
| Cleanup | PV/PVC/Pod | 테스트 잔존 자원 없음 |

샘플 SELECT만으로 업무 SQL 전체가 검증되는 것은 아님. 실제 업무 실행 시 BigQuery APPEND/DROP 권한과 병렬 실행 리스크 별도 검증.

## 6. 전체 과제 절체할 때만: 링크 교체 (1차에서는 금지)

**운영 승인을 받고 Cron 신규 시작 중지·기존 실행 작업 확인 후 진행.** 아래 명령은 1차 PoC에서 실행하지 말 것.

~~~bash
cd /ssw/dlk
test -L client_gke || { echo 'client_gke가 symlink가 아님'; exit 1; }
OLD_TARGET="$(readlink client_gke)"
printf '%s\n' "$OLD_TARGET" > /ssw/dlk/.client_gke_pre_cutover_target
test -x client-gke-auto || exit 1

ln -s client-gke-auto client_gke.next
mv -Tf client_gke.next client_gke
readlink -f client_gke
~~~

원복(신규 작업 중단 후 이전 링크 복원):

~~~bash
cd /ssw/dlk
OLD_TARGET="$(cat /ssw/dlk/.client_gke_pre_cutover_target)"
test -n "$OLD_TARGET" || exit 1
ln -s "$OLD_TARGET" client_gke.rollback
mv -Tf client_gke.rollback client_gke
readlink -f client_gke
~~~

공통 링크 절체는 30개 전체 신규 배치 실행에 영향을 줄 수 있으므로 RSVP만 성공한 상태에서 자동 절체하지 않는다.

## 7. 참고 실행 예 (첨부 기록)

이는 2026-10-22 첨부 내용의 실행 예이며, 새 GCP 작업을 실제 실행한 결과로 오인해서는 안 됩니다.

~~~bash
# 원본 run-gke.sh가 --dry-run을 지원하는 것으로 확인되면 사용
# bash /mnt/batch_gke/l2_gke_sh/rsvp/GP_L2RSVP_001_1/run-gke.sh \
#   --dry-run 20261016 20261016 20261016 180000 \
#   0 4 16 /home/jupyter/GP_L2RSVP_001_1/python python bq_auth_smoke.py
~~~

| 항목 | 첨부 로그 값 |
|---|---|
| KUBECONFIG (과거 첨부 로그) | /home/admin_sonmap_net/.kube/config_l2comn-autopilot |
| 이번 실행 사용자 | user01@sonmap.net (Kubeconfig는 현재 Linux 사용자의 $HOME 기준) |
| NAMESPACE | l2comm-batch |
| KSA | ksa-l2comm-batch |
| 이미지 | asia-northeast3-docker.pkg.dev/gcp-prod-edp-hub-vpchost/ar-l2comm-python/python-bq-batch:v1 |
| CPU/MEM/GPU | 4 / 16Gi / 0 |
| NFS_SERVER | 172.32.10.2 (관리 VM IP와 동일, 재확인 필요) |
| NFS_PATH / POD_MOUNT | /batch_gke/l2/rsvp / /home/jupyter |
| PVC | 20Gi / ROX / Bound |
| Pod | Pending → Running → Succeeded |
| 정리 | Pod / PVC / PV delete |
| 배치 반환 | SUCCESS 및 client_gke 정상 종료 (첨부 출력) |

## 8. 증적과 담당

- GKE: cluster describe, context/endpoint, kubectl nodes/pods/events — 플랫폼 담당
- AR: ImagePull 결과 및 이미지 태그 — Edge 담당
- NFS: PV/PVC 상태, Mount, 키 파일 이름·권한만 기록 — 네트워크/스토리지 담당
- BQ: Job ID, 프로젝트, 테이블, 성공 로그 — 데이터 담당
- 배치: Cron 인자, 실행 파일 checksum, 종료코드, 처리 건수 — Linux/업무 담당
- 실패하면 ImagePullBackOff, FailedMount, GKE API 403/EOF, BigQuery 403, 쿼리 오류를 분리 기록

**원칙:** 운영 GKE 생성, NFS 방화벽, IAM, 실행기 설치·절체는 관리자 승인 후 현장에서 수행.
