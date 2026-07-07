export const blankSource = {
  id: '',
  label: '',
  kind: 'gitlab',
  url: 'http://wish.mirero.co.kr',
  project_id: '',
  token: '',
  token_header: 'PRIVATE-TOKEN',
  dev_branch: '',
  release_branch: '',
  themes: 'intro,requirements,architecture-overview,component-diagram',
  owner_email: '',
  schedule_cron: '',
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
  url: 'http://wish.mirero.co.kr/mirero/project/pcc/product-common',
  project_id: '',
  project_path: 'mirero/project/pcc/product-common',
  token: '',
  token_header: 'PRIVATE-TOKEN',
  default_branch: 'master',
  enabled: false,
};

export function fieldValue(obj, key) {
  const value = obj?.[key];
  return Array.isArray(value) ? value.join(',') : (value ?? '');
}
