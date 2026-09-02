import React from 'react';
import { Zap, Globe, FileVideo, Subtitles, Youtube, Instagram, Check, ChevronDown, Languages, Type, Scissors, Facebook, Linkedin } from 'lucide-react';
import { useTranslation } from "./state/LanguageContext";
import { useNavigate} from "react-router-dom";

const TikTokIcon = ({ size = 16, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" className={className}>
    <path d="M19.589 6.686a4.793 4.793 0 0 1-3.77-4.245V2h-3.445v13.672a2.896 2.896 0 0 1-5.201 1.743l-.002-.001.002.001a2.895 2.895 0 0 1 3.183-4.51v-3.5a6.329 6.329 0 0 0-5.394 10.692 6.33 6.33 0 0 0 10.857-4.424V8.687a8.182 8.182 0 0 0 4.773 1.526V6.79a4.831 4.831 0 0 1-1.003-.104z" />
  </svg>
);

const FeatureCard = ({ icon: Icon, title, description }) => (
  <div className="group bg-surface/50 backdrop-blur-xl border border-slate-300 dark:border-white/10 rounded-2xl p-6 hover:border-primary/30 transition-all duration-300 hover:shadow-lg hover:shadow-primary/5">
    <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center mb-4 group-hover:bg-primary/20 transition-colors">
      <Icon size={24} className="text-primary" />
    </div>
    <h3 className="title-contrast text-lg font-semibold mb-2">{title}</h3>
    <p className="text-slate-500 dark:text-zinc-400 text-sm leading-relaxed">{description}</p>
  </div>
);

const StepCard = ({ number, title, description }) => (
  <div className="flex gap-4">
    <div className="flex-shrink-0 w-10 h-10 rounded-full bg-primary/20 border border-primary/30 flex items-center justify-center text-primary font-bold text-sm">
      {number}
    </div>
    <div>
      <h3 className="title-contrast font-semibold mb-1">{title}</h3>
      <p className="text-slate-500 dark:text-zinc-400 text-sm leading-relaxed">{description}</p>
    </div>
  </div>
);

const ComparisonRow = ({ feature, Vireel, opusclip, kapwing }) => (
  <tr className="border-b border-slate-200 dark:border-white/5">
    <td className="py-3 px-4 text-sm text-slate-700 dark:text-zinc-300">{feature}</td>
    <td className="py-3 px-4 text-center">{Vireel}</td>
    <td className="py-3 px-4 text-center">{opusclip}</td>
    <td className="py-3 px-4 text-center">{kapwing}</td>
  </tr>
);

const FAQItem = ({ question, answer, isOpen, onClick }) => (
  <div className="border border-slate-300 dark:border-white/10 rounded-xl overflow-hidden">
    <button
      onClick={onClick}
      className="w-full flex items-center justify-between px-6 py-4 text-left hover:bg-white/5 transition-colors"
    >
      <span className="text-white font-medium pr-4">{question}</span>
      <ChevronDown size={18} className={`text-slate-500 dark:text-zinc-400 flex-shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
    </button>
    {isOpen && (
      <div className="px-6 pb-5">
        <p className="faq-answer text-slate-500 dark:text-zinc-400 text-sm leading-relaxed">{answer}</p>
      </div>
    )}
  </div>
);

export default function Landing({ onLaunchApp }) {
  const [openFaq, setOpenFaq] = React.useState(null);
  const { t } = useTranslation();
  const navigate = useNavigate();

  const features = [
    {
      icon: Scissors,
      title: t("landing.feature1"),
      description: t("landing.feature1Desc")
    },
    {
      icon: Subtitles,
      title: t("landing.feature2"),
      description: t("landing.feature2Desc")
    },
    {
      icon: Languages,
      title: t("landing.feature3"),
      description: t("landing.feature3Desc")
    },
    {
      icon: Type,
      title: t("landing.feature4"),
      description: t("landing.feature4Desc")
    },
    {
      icon: Zap,
      title: t("landing.feature5"),
      description: t("landing.feature5Desc")
    },
    {
      icon: Globe,
      title: t("landing.feature6"),
      description: t("landing.feature6Desc")
    },
/*    {
      icon: Sparkles,
      title: "Générateur de vidéos UGC IA",
      description: "Générez des vidéos marketing avec des acteurs IA pour tout produit ou entreprise. Collez une URL ou décrivez votre produit — l'IA écrit le script, génère un avatar réaliste avec synchronisation labiale, ajoute des b-roll, des sous-titres et des superpositions accrocheuses. À partir de 0,65 $/vidéo."
    },
    {
      icon: FileVideo,
      title: "Acteurs IA et Synchronisation Labiale",
      description: "Choisissez parmi une galerie d'acteurs générés par l'IA ou téléversez votre propre photo. Le pipeline génère une vidéo de tête parlante avec des mouvements naturels et une voix off synchronisée en anglais ou en espagnol. Deux modes : Économique (0,65 $) et Premium (2,00 $)."
    } */
  ];

  const steps = [
    { title: t("landing.step1"), description: t("landing.step1Desc") },
    { title: t("landing.step2"), description: t("landing.step2Desc") },
    { title: t("landing.step3"), description: t("landing.step3Desc") },
    { title: t("landing.step4"), description: t("landing.step4Desc") },
    { title: t("landing.step5"), description: t("landing.step5Desc") }
  ];

  const faqs = [
    {
      question: t("landing.faq1"),
      answer: t("landing.faq1Desc"),
    },
    {
      question: t("landing.faq2"),
      answer: t("landing.faq2Desc"),
    },
    {
      question: t("landing.faq3"),
      answer: t("landing.faq3Desc"),
    },
    {
      question: t("landing.faq4"),
      answer: t("landing.faq4Desc"),
    },
    {
      question: t("landing.faq5"),
      answer: t("landing.faq5Desc"),
    },
    {
      question: t("landing.faq6"),
      answer: t("landing.faq6Desc"),
    },
    {
      question: t("landing.faq7"),
      answer: t("landing.faq7Desc"),
    },
    {
      question: t("landing.faq8"),
      answer: t("landing.faq8Desc"),
    },
    {
      question: t("landing.faq9"),
      answer: t("landing.faq9Desc"),
    },
    {
      question: t("landing.faq10"),
      answer: t("landing.faq10Desc"),
    },
    {
      question: t("landing.faq11"),
      answer: t("landing.faq11Desc"),
    },
    {
      question: t("landing.faq12"),
      answer: t("landing.faq12Desc"),
    },
    {
      question: t("landing.faq13"),
      answer: t("landing.faq13Desc"),
    },
    {
      question: t("landing.faq14"),
      answer: t("landing.faq14Desc"),
    },
    {
      question: t("landing.faq15"),
      answer: t("landing.faq15Desc"),
    },
    {
      question: t("landing.faq16"),
      answer: t("landing.faq16Desc"),
    },
    {
      question: t("landing.faq17"),
      answer: t("landing.faq17Desc"),
    }
  ];

  const checkIcon = <Check size={16} className="text-green-400 mx-auto" />;
  const xIcon = <span className="text-slate-400 dark:text-zinc-500 text-sm">Paid</span>;

  return (
    <div className="min-h-screen bg-background text-slate-900 dark:text-white">
      {/* Navigation */}
      <nav className="fixed top-0 w-full z-50 bg-background/80 backdrop-blur-xl border-b border-slate-200 dark:border-white/5">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <img src="/icone.png" alt="Vireel logo" className="w-8 h-8" />
            <span className="text-lg font-bold">VIREEL</span>
          </div>
          <div className="hidden md:flex items-center gap-8 text-sm text-slate-500 dark:text-zinc-400">
            <a href="#features" className="hover:text-white transition-colors">{t("landing.feature")}</a>
            <a href="#how-it-works" className="hover:text-white transition-colors">{t("landing.howItWorks")}</a>
            <a href="#comparison" className="hover:text-white transition-colors">{t("landing.prix")}</a>
            <a href="#faq" className="hover:text-white transition-colors">{t("landing.faq")}</a>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate("/login")}
              className="bg-primary hover:bg-blue-600 text-white dark:text-white px-5 py-2 rounded-xl text-sm font-medium transition-all active:scale-[0.98] shadow-lg shadow-primary/20"
            >{t("landing.launchApp")}</button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-6">
        <div className="max-w-5xl mx-auto text-center">

          <h1 className="text-4xl md:text-6xl lg:text-7xl font-bold leading-tight mb-6 tracking-tight">
            {t("landing.appDescription")}
            <span className="bg-gradient-to-r from-primary via-purple-400 to-pink-500 bg-clip-text text-transparent">{t("landing.appDescription2")}</span>
          </h1>

          <p className="hero-description text-lg md:text-xl text-slate-500 dark:text-zinc-400 max-w-3xl mx-auto mb-10 leading-relaxed">
            {t("landing.appDescription3")}
          </p>

          {/* Platform Icons */}
          <div className="flex items-center justify-center gap-6 text-slate-400 dark:text-zinc-500">
            <span className="text-sm">{t("landing.exportTo")}</span>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-1.5 text-slate-500 dark:text-zinc-400">
                <TikTokIcon size={18} />
                <span className="text-sm">TikTok</span>
              </div>
              <div className="flex items-center gap-1.5 text-slate-500 dark:text-zinc-400">
                <Instagram size={18} />
                <span className="text-sm">Instagram</span>
              </div>
              <div className="flex items-center gap-1.5 text-slate-500 dark:text-zinc-400">
                <Youtube size={18} />
                <span className="text-sm">Youtube</span>
              </div>
              <div className="flex items-center gap-1.5 text-slate-500 dark:text-zinc-400">
                <Facebook size={18} />
                <span className="text-sm">Facebook</span>
              </div>
              <div className="flex items-center gap-1.5 text-slate-500 dark:text-zinc-400">
                <Linkedin size={18} />
                <span className="text-sm">LinkedIn</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-2 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-2">
            {features.map((feature, i) => (
              <FeatureCard key={i} {...feature} />
            ))}
          </div>
        </div>
      </section>


      {/* How It Works Section */}
      <section id="how-it-works" className="py-10 px-6">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-14">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">{t("landing.howItWorks")}</h2>
            <p className="text-slate-500 dark:text-zinc-400 max-w-2xl mx-auto">{t("landing.stepDescription")}</p>
          </div>
          <div className="space-y-8">
            {steps.map((step, i) => (
              <StepCard key={i} number={i + 1} {...step} />
            ))}
          </div>
        </div>
      </section>

      {/* Comparison Table */}
      <section id="comparison" className="py-20 px-6 bg-surface/20">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-14">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">{t("landing.priceTitle")}</h2>
            <p className="text-slate-500 dark:text-zinc-400 max-w-2xl mx-auto">{t("landing.priceDesc")}</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-300 dark:border-white/10">
                  <th className="py-3 px-4 text-left text-sm text-slate-500 dark:text-zinc-400 font-medium">{t("landing.feature")}</th>
                  <th className="py-3 px-4 text-center text-sm font-medium">
                    <span className="text-primary">{t("landing.silver")}</span>
                  </th>
                  <th className="py-3 px-4 text-center text-sm text-slate-500 dark:text-zinc-400 font-medium">{t("landing.gold")}</th>
                  <th className="py-3 px-4 text-center text-sm text-slate-500 dark:text-zinc-400 font-medium">{t("landing.ultimate")}</th>
                </tr>
              </thead>
              <tbody>
                <ComparisonRow feature={t("landing.prix")} Vireel={<span className="text-green-400 font-semibold">9.99€ / mois</span>} opusclip={<span className="font-semibold">24.99€ / mois</span>} kapwing={<span className="font-semibold">49.99€ / mois</span>} />
                <ComparisonRow feature={t("landing.storage")} Vireel={<span className="text-green-400 font-semibold">10 Go</span>} opusclip={<span className="font-semibold">50 Go</span>} kapwing={<span className="font-semibold">100 Go</span>} />
                <ComparisonRow feature={t("landing.viral")} Vireel={checkIcon} opusclip={checkIcon} kapwing={checkIcon} />
                <ComparisonRow feature={t("landing.shorts")} Vireel={checkIcon} opusclip={checkIcon} kapwing={checkIcon} />
                <ComparisonRow feature={t("landing.subtitles")} Vireel={checkIcon} opusclip={checkIcon} kapwing={checkIcon} />
                <ComparisonRow feature={t("landing.translation")} Vireel={checkIcon} opusclip={checkIcon} kapwing={checkIcon} />
                <ComparisonRow feature={t("landing.iaEffects")} Vireel={checkIcon} opusclip={checkIcon} kapwing={checkIcon} />
                <ComparisonRow feature={t("landing.hooks")} Vireel={checkIcon} opusclip={checkIcon} kapwing={checkIcon} />
                <ComparisonRow feature={t("landing.social")} Vireel={checkIcon} opusclip={checkIcon} kapwing={checkIcon} />
                <ComparisonRow feature={t("landing.watermark")} Vireel={checkIcon} opusclip={checkIcon} kapwing={checkIcon} />
                <ComparisonRow feature={t("landing.youtubeLink")} Vireel={checkIcon} opusclip={checkIcon} kapwing={checkIcon} />

              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* Use Cases */}
      <section className="py-10 px-6">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-14">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">{t("landing.vireelWho")}</h2>
            <p className="text-slate-500 dark:text-zinc-400 max-w-2xl mx-auto">{t("landing.vireelWhoDesc")}</p>
          </div>
          <div className="grid md:grid-cols-3 gap-5">
            {[
              {
                title: t("landing.contentCreators"),
                description: t("landing.contentCreatorsDesc"),
                icon: Youtube
              },
              {
                title: t("landing.socialManagers"),
                description: t("landing.socialManagersDesc"),
                icon: Instagram
              },
              {
                title: t("landing.podcastersEducators"),
                description: t("landing.podcastersEducatorsDesc"),
                icon: FileVideo
              }
            ].map((useCase, i) => (
              <div key={i} className="bg-surface/50 border border-slate-300 dark:border-white/10 rounded-2xl p-6">
                <useCase.icon size={24} className="text-primary mb-4" />
                <h3 className="title-contrast text-lg font-semibold mb-2">{useCase.title}</h3>
                <p className="text-slate-500 dark:text-zinc-400 text-sm leading-relaxed">{useCase.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ Section */}
      <section id="faq" className="py-10 px-6 bg-surface/20">
        <div className="max-w-3xl mx-auto">
          <div className="text-center mb-14">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">{t("landing.faqTitle")}</h2>
            <p className="text-slate-500 dark:text-zinc-400">{t("landing.faqDesc")}</p>
          </div>
          <div className="space-y-3">
            {faqs.map((faq, i) => (
              <FAQItem
                key={i}
                question={faq.question}
                answer={faq.answer}
                isOpen={openFaq === i}
                onClick={() => setOpenFaq(openFaq === i ? null : i)}
              />
            ))}
          </div>
        </div>
      </section>


      {/* Footer */}
      <footer className="border-t border-slate-200 dark:border-white/5 py-10 px-6">
        <div className="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <img src="/icone.png" alt="Vireel" className="w-6 h-6" />
            <span className="text-sm text-slate-500 dark:text-zinc-400">© 2026 VIREEL — Kamga & Fils Group. Tous droits réservés.</span>
          </div>
          <div className="flex items-center gap-6 text-sm text-slate-400 dark:text-zinc-500">
            <a href="https://docs.vireel.co/confidentialite.html" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">{t("landing.confidentialite")}</a>
            <a href="https://docs.vireel.co/remboursement.html" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">{t("landing.remboursement")}</a>
            <a href="https://docs.vireel.co/cgu.html" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">{t("landing.conditions")}</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
