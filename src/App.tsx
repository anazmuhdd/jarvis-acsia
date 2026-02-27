import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AppProvider } from "./context/AppContext";
import { Dashboard } from "./pages/Dashboard";
import { AllArticles } from "./pages/AllArticles";

function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/articles" element={<AllArticles />} />
        </Routes>
      </BrowserRouter>
    </AppProvider>
  );
}

export default App;
