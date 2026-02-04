import { render } from 'solid-js/web';
import App from './App';

const root = document.getElementById('root');
if (root) {
  // Clear the static loader before mounting
  root.innerHTML = '';
  render(() => <App />, root);
}
