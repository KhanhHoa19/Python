import App from './App.tsx';
import { useAuth } from './hooks/useAuth.ts';
import { LoginPage } from './pages/LoginPage.tsx';

/** Shows the sign-in form until someone is signed in, then the app. */
export function Root() {
  const auth = useAuth();
  if (!auth.session) return <LoginPage notice={auth.notice} onAuthenticated={auth.signIn} />;
  return <App key={auth.session.user.id} user={auth.session.user} onLogout={() => auth.signOut()} />;
}
