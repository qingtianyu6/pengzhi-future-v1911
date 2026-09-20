import banner from '../assets/images/bottom-banner.png'
import HandNote from '../components/HandNote'

export default function BottomBanner() {
  return (
    <section className="bottom-banner">
      <img src={banner} alt="农业大棚与山野"/>
      <div className="bottom-banner__veil" />
      <div className="bottom-banner__copy">让技术扎根大棚，<br/>让种植更有底气。</div>
      <HandNote className="bottom-banner__note">科技，<br/>让农业更美好</HandNote>
    </section>
  )
}
