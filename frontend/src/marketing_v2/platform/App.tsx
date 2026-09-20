import './styles.css'
import Header from './components/Header'
import PlatformHeroSection from './sections/PlatformHeroSection'
import WhySection from './sections/WhySection'
import CapabilitySection from './sections/CapabilitySection'
import FeaturesSection from './sections/FeaturesSection'
import FlowSection from './sections/FlowSection'
import RealSceneSection from './sections/RealSceneSection'
import PlatformBottomBanner from './sections/PlatformBottomBanner'

export default function App() {
  return (
    <div className="pz-platform-v2 site-shell">
      <Header />
      <main>
        <PlatformHeroSection />
        <WhySection />
        <CapabilitySection />
        <FeaturesSection />
        <FlowSection />
        <RealSceneSection />
        <PlatformBottomBanner />
      </main>
    </div>
  )
}
