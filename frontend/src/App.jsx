import "./App.css";
import ChatPage from "./components/Chatpage";
import { AuthProvider } from "./context/AuthContext";
import AuthModal from "./components/AuthModal";
import ProfileModal from "./components/ProfileModal";

function App() {
  return (
    <AuthProvider>
      <ChatPage />
      <AuthModal />
      <ProfileModal />
    </AuthProvider>
  );
}

export default App;