import { useEffect, useState } from "react";
import { Briefcase, Quote, Sparkles, Loader2 } from "lucide-react";
import { format } from "date-fns";
import { useAppContext } from "../context/AppContext";

export function ProfileCard() {
  const { profile, recap, recapLoading } = useAppContext();
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="py-2">
      {/* Profile row */}
      <div className="flex items-center gap-4 mb-3">
        {!profile ? (
          <>
            <div className="w-10 h-10 rounded-full shrink-0 ring-4 ring-gray-50 shadow-sm bg-gray-50 flex items-center justify-center">
              <Loader2 size={16} className="text-gray-400 animate-spin" />
            </div>
            <div className="flex flex-col flex-1 gap-2 pt-1">
              <div className="h-4 bg-gray-100 rounded w-32 animate-pulse"></div>
              <div className="h-3 bg-gray-50 rounded w-20 animate-pulse"></div>
            </div>
          </>
        ) : (
          <>
            <div className="w-10 h-10 rounded-full overflow-hidden shrink-0 ring-4 ring-gray-50 shadow-sm">
              <img src={profile.photoUrl} alt={profile.displayName} className="w-full h-full object-cover" />
            </div>
            <div>
              <p className="font-bold text-[1.1rem] text-gray-900 leading-tight">{profile.displayName}</p>
              <p className="flex items-center gap-1.5 text-xs text-gray-500 mt-1">
                <Briefcase size={12} className="text-[#1a73e8]" /> {profile.department}
              </p>
            </div>
          </>
        )}
      </div>

      {/* Live clock */}
      <p className="text-base font-bold text-gray-900 leading-none tracking-tight mb-2">
        {format(now, "HH:mm")}
      </p>
      <p className="text-base text-gray-400 mb-6">
        {format(now, "EEEE, MMMM d, yyyy")}
      </p>

      {/* Divider */}
      <div className="h-px bg-gray-100 mb-6" />

      {/* Recap Section */}
      <div className="bg-gray-50 rounded-xl p-4 border border-gray-100">
        <div className="flex items-center justify-between mb-2.5">
          <div className="flex items-center gap-2">
            <Sparkles size={14} className="text-[#1a73e8]" />
            <span className="text-[0.7rem] font-bold text-[#1a73e8] uppercase tracking-wider">Daily Recap</span>
          </div>
          <Quote size={13} className="text-[#1a73e8] opacity-30" />
        </div>
        
        {recapLoading ? (
          <div className="flex items-center gap-2.5 py-2">
            <Loader2 size={13} className="text-gray-400 animate-spin" />
            <span className="text-[0.8rem] text-gray-400">Generating intelligence...</span>
          </div>
        ) : (
          <p className="text-[0.82rem] leading-[1.6] text-gray-600">
            {recap || "No recap available for today."}
          </p>
        )}
      </div>
    </div>
  );
}
