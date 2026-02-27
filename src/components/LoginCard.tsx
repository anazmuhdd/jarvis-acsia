import { LogIn } from "lucide-react";
import { motion } from "framer-motion";
import { useMsal } from "@azure/msal-react";
import { loginRequest } from "../services/msalConfig";

export function LoginCard() {
  const { instance } = useMsal();

  const handleLogin = () => {
    instance.loginRedirect(loginRequest).catch(e => console.error(e));
  };

  return (
    <div className="h-screen flex flex-col items-center justify-center bg-[#f4f4f5]">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="p-12 bg-white rounded-2xl shadow-[0_10px_40px_rgba(0,0,0,0.12)] text-center max-w-sm w-full mx-4">
        <div className="w-16 h-16 bg-[#e8f0fe] rounded-2xl flex items-center justify-center mx-auto mb-6">
          <LogIn size={32} color="#1a73e8" />
        </div>
        <h2 className="text-2xl font-extrabold text-gray-900 mb-3">Welcome Back</h2>
        <p className="text-gray-500 text-sm mb-8 leading-relaxed">
          Sign in with your Microsoft account to access your professional intelligence dashboard.
        </p>
        <button
          onClick={handleLogin}
          className="w-full flex items-center justify-center gap-2.5 bg-[#1a73e8] hover:bg-[#1557b0]
                     text-white font-semibold text-sm px-6 py-3 rounded-xl transition-all
                     hover:-translate-y-0.5 hover:shadow-lg">
          Sign in with Microsoft
        </button>
      </motion.div>
    </div>
  );
}
