import './styles.css'
import Header from './components/Header'
import HeroSection from './sections/HeroSection'
import EnvironmentSection from './sections/EnvironmentSection'
import DiseaseSection from './sections/DiseaseSection'
import FarmSection from './sections/FarmSection'
import DecisionSection from './sections/DecisionSection'
import ArchiveSection from './sections/ArchiveSection'
import BottomBanner from './sections/BottomBanner'

export default function App() {
  return (
    <div className="pz-features-v2 site-shell">
      <Header />
      <main>
        <HeroSection />
        <div id="core" className="core-panel">
          <EnvironmentSection />
          <DiseaseSection />
          <FarmSection />
          <DecisionSection />
          <ArchiveSection />
        </div>
        <BottomBanner />
      </main>
    </div>
  )
}
