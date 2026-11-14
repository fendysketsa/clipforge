import assert from 'node:assert/strict';
import test from 'node:test';
import vm from 'node:vm';
import { resolveStudioTheme, THEME_BOOTSTRAP, THEME_STORAGE_KEY } from '../lib/studioTheme.ts';

test('an explicit preference takes priority over the system setting', () => {
  assert.equal(resolveStudioTheme('light',true),'light');
  assert.equal(resolveStudioTheme('dark',false),'dark');
  assert.equal(resolveStudioTheme(null,true),'dark');
  assert.equal(resolveStudioTheme('invalid',false),'light');
});

test('the head bootstrap applies the stored preference before React renders', () => {
  const root={dataset:{}};
  vm.runInNewContext(THEME_BOOTSTRAP,{document:{documentElement:root},localStorage:{getItem(key){assert.equal(key,THEME_STORAGE_KEY);return 'light';}},matchMedia:()=>({matches:true})});
  assert.equal(root.dataset.theme,'light');
});

test('blocked browser storage and invalid preferences safely follow the system', () => {
  for(const preference of ['invalid',null,'blocked']){
    const root={dataset:{}};
    vm.runInNewContext(THEME_BOOTSTRAP,{document:{documentElement:root},localStorage:{getItem(){if(preference==='blocked')throw new Error('Storage disabled');return preference;}},matchMedia:()=>({matches:true})});
    assert.equal(root.dataset.theme,'dark');
  }
});
