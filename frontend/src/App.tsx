import { useMemo, useState, type ReactNode } from 'react'

type Policy = {
  id: number
  title: string
  departmentName: string
  category: string
  status: 'D-5' | 'D-12' | '상시모집' | 'D-3'
  targetAge: string
  targetIncome: string
  applicationPeriod: string
  viewCount: number
  sourceSystem: 'GOV24' | 'EMPLOYMENT24' | 'LOCAL'
  supportType: string
  summary: string
  flag: 'urgent' | 'new' | 'relaxed'
}

const policies: Policy[] = [
  {
    id: 1,
    title: '2025 청년월세 특별지원',
    departmentName: '국토교통부',
    category: '주거',
    status: 'D-5',
    targetAge: '만 19~34세',
    targetIncome: '중위 120% 이하',
    applicationPeriod: '2025.03.01 ~ 2025.05.30',
    viewCount: 12840,
    sourceSystem: 'GOV24',
    supportType: '현금',
    summary: '월 최대 20만원, 최대 12개월간 청년의 주거비를 지원합니다.',
    flag: 'urgent',
  },
  {
    id: 2,
    title: '청년도약계좌 가입 지원',
    departmentName: '금융위원회',
    category: '금융',
    status: '상시모집',
    targetAge: '만 19~34세',
    targetIncome: '개인소득 7,500만원 이하',
    applicationPeriod: '매월 가입 신청',
    viewCount: 9462,
    sourceSystem: 'GOV24',
    supportType: '금융',
    summary: '정부기여금과 비과세 혜택으로 청년의 중장기 자산 형성을 돕습니다.',
    flag: 'relaxed',
  },
  {
    id: 3,
    title: '청년 일경험 지원사업',
    departmentName: '고용노동부',
    category: '취업',
    status: 'D-12',
    targetAge: '만 15~34세',
    targetIncome: '소득 무관',
    applicationPeriod: '2025.04.01 ~ 예산 소진 시',
    viewCount: 8291,
    sourceSystem: 'EMPLOYMENT24',
    supportType: '수당',
    summary: '기업탐방부터 인턴형까지 직무 경험과 참여 수당을 함께 제공합니다.',
    flag: 'new',
  },
  {
    id: 4,
    title: '청년문화예술패스',
    departmentName: '문화체육관광부',
    category: '문화',
    status: 'D-3',
    targetAge: '만 19세',
    targetIncome: '소득 무관',
    applicationPeriod: '2025.03.06 ~ 2025.05.31',
    viewCount: 7718,
    sourceSystem: 'LOCAL',
    supportType: '바우처',
    summary: '공연과 전시 관람에 사용할 수 있는 문화예술 관람비를 지원합니다.',
    flag: 'urgent',
  },
]

const categories = [
  { icon: 'home', title: '주거·우대 혜택', count: 128, desc: '월세 · 행복주택 · 전세대출', tone: 'blue' },
  { icon: 'briefcase', title: '취업·창업 지원', count: 94, desc: '취업지원 · 직업훈련 · 창업', tone: 'green' },
  { icon: 'wallet', title: '금융·자산 형성', count: 76, desc: '도약계좌 · 공제 · 정책금융', tone: 'purple' },
  { icon: 'book', title: '교육·문화·복지', count: 112, desc: '문화패스 · 수강료 · 건강검진', tone: 'amber' },
]

function Icon({ name, size = 20 }: { name: string; size?: number }) {
  const paths: Record<string, ReactNode> = {
    search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></>,
    bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" /><path d="M10 21h4" /></>,
    user: <><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>,
    chevron: <path d="m9 18 6-6-6-6" />,
    down: <path d="m6 9 6 6 6-6" />,
    home: <><path d="m3 11 9-8 9 8" /><path d="M5 10v10h14V10M9 20v-6h6v6" /></>,
    briefcase: <><rect x="3" y="7" width="18" height="13" rx="2" /><path d="M8 7V4h8v3M3 12h18M10 12v2h4v-2" /></>,
    wallet: <><path d="M4 5h14a2 2 0 0 1 2 2v13H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z" /><path d="M16 11h6v5h-6a2.5 2.5 0 0 1 0-5Z" /></>,
    book: <><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V4H6.5A2.5 2.5 0 0 0 4 6.5v13Z" /><path d="M8 8h8M8 12h6" /></>,
    heart: <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8l1.1 1.1L12 21l7.8-7.5 1.1-1.1a5.5 5.5 0 0 0-.1-7.8Z" />,
    building: <><path d="M3 21h18M6 21V8l6-5 6 5v13" /><path d="M9 11h1m4 0h1m-6 4h1m4 0h1m-4 6v-3h2v3" /></>,
    menu: <path d="M4 6h16M4 12h16M4 18h16" />,
    check: <path d="m5 12 4 4L19 6" />,
    arrow: <path d="M5 12h14m-6-6 6 6-6 6" />,
    external: <><path d="M15 3h6v6M10 14 21 3" /><path d="M18 13v7H4V6h7" /></>,
  }
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>
}

function Button({ children, className = '', ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button className={className} {...props}>{children}</button>
}

function App() {
  const [menuOpen, setMenuOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [region, setRegion] = useState('전국')
  const [age, setAge] = useState('만 19~34세')
  const [job, setJob] = useState('취업 상태')
  const [income, setIncome] = useState('소득 구간')
  const [activeTab, setActiveTab] = useState('전체')
  const [bookmarks, setBookmarks] = useState<number[]>([])
  const [searched, setSearched] = useState('')

  const visiblePolicies = useMemo(() => {
    return policies.filter((policy) => {
      const tabMatch = activeTab === '전체' || (activeTab === '마감 임박' && policy.flag === 'urgent') || (activeTab === '신규 등록' && policy.flag === 'new') || (activeTab === '소득조건 완화' && policy.flag === 'relaxed')
      const queryMatch = !searched || `${policy.title} ${policy.departmentName} ${policy.category}`.includes(searched)
      return tabMatch && queryMatch
    })
  }, [activeTab, searched])

  const submitSearch = (event: React.FormEvent) => {
    event.preventDefault()
    setSearched(query.trim())
  }

  return (
    <div className="app-shell">
      <div className="official-bar">
        <div className="container official-inner">
          <span className="flag-mark">대한민국</span>
          <span>이 누리집은 대한민국 공식 전자정부 누리집입니다.</span>
          <span className="official-meta">공공데이터 실시간 연동 · 2025.05.22 기준</span>
        </div>
      </div>

      <header className="header">
        <div className="container header-inner">
          <a className="brand" href="#" aria-label="청년모아 홈">
            <span className="brand-icon"><Icon name="building" size={25} /></span>
            <span>청년모아</span>
            <span className="brand-badge">공공 마이데이터 연동</span>
          </a>
          <nav className={menuOpen ? 'gnb is-open' : 'gnb'} aria-label="주요 메뉴">
            <a href="#policies">청년정책 전체보기</a>
            <a href="#search">맞춤 지원금 진단</a>
            <a href="#links">정부24/고용24 연계</a>
            <a href="#footer">고객센터/공지사항</a>
          </nav>
          <div className="utilities">
            <Button className="icon-button" aria-label="알림 3개"><Icon name="bell" /><span className="notification">3</span></Button>
            <span className="user-chip"><Icon name="user" size={17} /><b>홍길동 님</b><span>청년 연령 검증 완료</span></span>
            <Button className="mypage">마이페이지</Button>
          </div>
          <Button className="mobile-menu" onClick={() => setMenuOpen(!menuOpen)} aria-label="메뉴 열기"><Icon name="menu" /></Button>
        </div>
      </header>

      <main>
        <section className="hero" id="search">
          <div className="container hero-inner">
            <div className="eyebrow"><span className="pulse" /> 정부24 · 고용24 · 지자체 정책 통합 조회</div>
            <h1>청년 정책을 한곳에서,<br /><strong>나에게 맞는 혜택만</strong> 찾아보세요</h1>
            <p>연령, 소득, 거주지 조건에 맞는 공공 지원금 및 정책 데이터를 실시간으로 가져옵니다.</p>
            <form className="search-panel glass" onSubmit={submitSearch}>
              <div className="main-search">
                <Icon name="search" size={23} />
                <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="정책명 또는 키워드를 검색하세요 (예: 청년도약계좌, 월세지원)" aria-label="정책 검색어" />
                <Button className="search-button" type="submit"><Icon name="search" size={19} /><span>맞춤 정책 검색</span></Button>
              </div>
              <div className="filters">
                <label><span>지역</span><select value={region} onChange={(event) => setRegion(event.target.value)}><option>전국</option><option>서울</option><option>경기</option><option>인천</option><option>지방 자치단체</option></select></label>
                <label><span>연령</span><select value={age} onChange={(event) => setAge(event.target.value)}><option>만 19~34세</option><option>만 15~29세</option><option>만 25~39세</option></select></label>
                <label><span>취업 상태</span><select value={job} onChange={(event) => setJob(event.target.value)}><option>취업 상태</option><option>미취업</option><option>재직자</option><option>창업자</option><option>학생</option></select></label>
                <label><span>소득 구간</span><select value={income} onChange={(event) => setIncome(event.target.value)}><option>소득 구간</option><option>중위소득 100% 이하</option><option>중위소득 120% 이하</option><option>무관</option></select></label>
              </div>
            </form>
            <div className="search-hint"><b>인기 검색어</b><button onClick={() => { setQuery('청년월세'); setSearched('청년월세') }}>청년월세</button><button onClick={() => { setQuery('청년도약계좌'); setSearched('청년도약계좌') }}>청년도약계좌</button><button onClick={() => { setQuery('취업'); setSearched('취업') }}>취업지원</button></div>
          </div>
        </section>

        <section className="container category-section" aria-labelledby="category-title">
          <div className="section-heading compact">
            <div><span className="section-kicker">분야별 정책 찾기</span><h2 id="category-title">어떤 지원이 필요하세요?</h2></div>
            <a href="#policies">전체 정책 410건 <Icon name="chevron" size={16} /></a>
          </div>
          <div className="category-grid">
            {categories.map((category) => (
              <button className={`category-card glass ${category.tone}`} key={category.title}>
                <span className="category-icon"><Icon name={category.icon} size={25} /></span>
                <span className="category-copy"><b>{category.title}</b><small>{category.desc}</small></span>
                <span className="counter">{category.count}<small>건</small></span>
                <Icon name="chevron" size={18} />
              </button>
            ))}
          </div>
        </section>

        <section className="container policies-section" id="policies">
          <div className="section-heading">
            <div><span className="section-kicker">청년들이 지금 가장 많이 보는</span><h2>인기 청년 정책 <strong>TOP 4</strong></h2></div>
            <div className="tabs" role="tablist">
              {['전체', '마감 임박', '신규 등록', '소득조건 완화'].map((tab) => <button key={tab} className={activeTab === tab ? 'active' : ''} onClick={() => setActiveTab(tab)} role="tab" aria-selected={activeTab === tab}>{tab}</button>)}
            </div>
          </div>
          {visiblePolicies.length ? (
            <div className="policy-grid">
              {visiblePolicies.map((policy) => (
                <article className="policy-card glass" key={policy.id}>
                  <div className="card-top">
                    <span className={`source ${policy.sourceSystem.toLowerCase()}`}>{policy.sourceSystem === 'GOV24' ? '정부24' : policy.sourceSystem === 'EMPLOYMENT24' ? '고용24' : '지자체'} API 연동</span>
                    <span className={policy.status === '상시모집' ? 'status open' : policy.status === 'D-3' || policy.status === 'D-5' ? 'status urgent' : 'status'}>{policy.status}</span>
                  </div>
                  <span className="department">{policy.departmentName} · {policy.category}</span>
                  <h3>{policy.title}</h3>
                  <p>{policy.summary}</p>
                  <div className="meta">
                    <span><b>연령</b>{policy.targetAge}</span>
                    <span><b>소득</b>{policy.targetIncome}</span>
                    <span><b>지원형태</b>{policy.supportType}</span>
                  </div>
                  <div className="period"><span>신청기간</span><b>{policy.applicationPeriod}</b><small>조회 {policy.viewCount.toLocaleString()}회</small></div>
                  <div className="card-actions">
                    <Button className={bookmarks.includes(policy.id) ? 'bookmark saved' : 'bookmark'} onClick={() => setBookmarks((items) => items.includes(policy.id) ? items.filter((id) => id !== policy.id) : [...items, policy.id])} aria-label={`${policy.title} 관심 정책 저장`}><Icon name="heart" size={20} /></Button>
                    <Button className="detail-button">상세보기 및 신청하기 <Icon name="arrow" size={18} /></Button>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="empty-state glass">
              <span className="empty-icon"><Icon name="search" size={30} /></span>
              <h3>검색 결과가 없습니다</h3>
              <p>검색어를 확인하거나 지역·연령·소득 조건을 넓혀보세요.</p>
              <Button onClick={() => { setQuery(''); setSearched(''); setActiveTab('전체') }}>검색 조건 초기화</Button>
            </div>
          )}
          {visiblePolicies.length > 0 && <div className="pagination" aria-label="페이지 선택"><button className="active">1</button><button>2</button><button>3</button><span>…</span><button>12</button><button className="next">다음 <Icon name="chevron" size={15} /></button></div>}
        </section>

        <section className="container integration-section" id="links">
          <div className="integration-card gov">
            <div><span className="integration-label">대한민국 대표 행정서비스</span><h2>정부24 바로가기</h2><p>중앙부처 및 지자체 혜택을 한 번에 확인하고 신청하세요.</p></div>
            <button aria-label="정부24 새 창으로 이동"><Icon name="external" /></button>
          </div>
          <div className="integration-card work">
            <div><span className="integration-label">고용서비스 통합 플랫폼</span><h2>고용24 바로가기</h2><p>취업 지원과 직업 훈련 수당을 맞춤 조회하세요.</p></div>
            <button aria-label="고용24 새 창으로 이동"><Icon name="external" /></button>
          </div>
        </section>
      </main>

      <footer id="footer">
        <div className="container footer-top">
          <div className="footer-brand"><span className="brand-icon"><Icon name="building" size={23} /></span><b>청년모아</b><p>흩어진 청년 정책을 쉽고 정확하게 연결합니다.</p></div>
          <div className="footer-links"><a href="#">이용약관</a><a href="#"><b>개인정보처리방침</b></a><a href="#">공공데이터 이용안내</a><a href="#">고객센터</a></div>
        </div>
        <div className="container footer-bottom">
          <p>행정안전부 정부24 · 고용노동부 고용24 · 공공데이터포털 연동 정보이며, 실제 신청 조건은 제공기관에서 최종 확인해 주세요.<br />© 2025 YouthMoa. All rights reserved.</p>
          <div className="contact"><span>정부민원안내</span><b>110</b><i /> <span>고용노동상담</span><b>1350</b></div>
        </div>
      </footer>
    </div>
  )
}

export default App
