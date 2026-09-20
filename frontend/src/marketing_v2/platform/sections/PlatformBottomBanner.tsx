import banner from '../assets/images/bottom-banner.png'

export default function PlatformBottomBanner() {
  return (
    <section className="platform-banner">
      <img src={banner} alt="晨曦下的温室与农田" />
      <div className="platform-banner__veil" />
      <div className="platform-banner__copy">从一座大棚出发，<br /><span>看见农业管理的每一步。</span><i /></div>
      <div className="platform-banner__note">科技，让农业更美好<i /></div>
    </section>
  )
}
