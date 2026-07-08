// 폼 기본값. 사내 URL을 하드코딩하지 않는다 — 사용자가 직접 채우도록 빈 값으로.
// 인스턴스/소스를 처음 등록하는 환경(GitHub, gitlab.com, 사내 GitLab 등)을 가리지 않는다.
export const blankSource = {
  id: '',
  label: '',
  kind: 'gitlab',
  url: '',
  project_id: '',
  token: '',
  token_header: 'PRIVATE-TOKEN',
  dev_branch: '',
  release_branch: '',
  themes: 'intro,requirements,architecture-overview,component-diagram',
  owner_email: '',
  schedule_cron: '',
  schedule_time: '20:00',
  schedule_weekdays: ['mon', 'tue', 'wed', 'thu', 'fri'],
  enabled: true,
};

export const blankInstance = {
  id: '',
  kind: 'gitlab',
  label: '',
  base_url: '',
  token: '',
  token_header: 'PRIVATE-TOKEN',
  enabled: true,
};

export const defaultDocTarget = {
  id: 'product-common',
  label: 'product-common',
  kind: 'gitlab',
  url: '',
  project_id: '',
  project_path: '',
  token: '',
  token_header: 'PRIVATE-TOKEN',
  default_branch: 'master',
  enabled: false,
};

export function fieldValue(obj, key) {
  const value = obj?.[key];
  return Array.isArray(value) ? value.join(',') : (value ?? '');
}
