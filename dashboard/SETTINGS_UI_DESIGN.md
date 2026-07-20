# Settings Page UI Design Document

## Layout Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                          SETTINGS                               │
│  Manage your account, appearance, and connected networks        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ 👤 ACCOUNT SETTINGS                                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ User ID:                                                        │
│ [00000000-0000-0000-0000-000000000000]  [Copy]                │
│ Your unique identifier in OpenShorts                            │
│                                                                 │
│ Email:                                                          │
│ ✉ [user@example.com                    ]                       │
│ Your login email address                                        │
│                                                                 │
│ Display Name:                                                   │
│ [John Doe                                ]  [Edit]             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ 🌙 APPEARANCE                                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ Choose how OpenShorts looks on your device                      │
│                                                                 │
│  ☀️          🌙          🖥️                                      │
│  Light      Dark       System                                   │
│  [Light]  [Dark]     [System✓]                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ 🔗 CONNECTED NETWORKS                                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ Connect your social media accounts to easily share your        │
│ creations directly from OpenShorts.                            │
│                                                                 │
│ ┌──────────────────┐  ┌──────────────────┐                    │
│ │ 💼 LinkedIn      │  │ 🎵 TikTok        │                    │
│ │ Professional     │  │ Millions of      │                    │
│ │ [Connected ✓]    │  │ viewers          │                    │
│ └──────────────────┘  └──────────────────┘                    │
│                                                                 │
│ ┌──────────────────┐  ┌──────────────────┐                    │
│ │ ▶️ YouTube       │  │ 👍 Facebook      │                    │
│ │ Upload to        │  │ Share with       │                    │
│ │ [Connected ✓]    │  │ community        │                    │
│ └──────────────────┘  └──────────────────┘                    │
│                                                                 │
│ ┌──────────────────┐                                          │
│ │ 📷 Instagram     │                                          │
│ │ Post to your     │                                          │
│ │ feed             │                                          │
│ └──────────────────┘                                          │
│                                                                 │
│ 💡 Note: Connected networks are stored locally in your         │
│ browser. Authentication happens securely via each platform.   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ 📊 SERVICE STATUS                                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ ✅ All services configured                                     │
│                                                                 │
│ Google Gemini        ● Ready                                   │
│ OpenAI              ● Ready                                   │
│ ElevenLabs          ● Not configured                           │
│ Upload-Post         ● Not configured                           │
│ AWS S3              ● Ready                                   │
│ Supabase            ● Ready                                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ ⚙️ API KEYS & SERVICES                                          │
│                                                                 │
│ All API keys (Gemini, ElevenLabs, etc.) are configured via     │
│ environment variables and are never exposed in the UI. Your    │
│ browser stores no credentials - only feature preferences.      │
└─────────────────────────────────────────────────────────────────┘
```

## Component States

### Account Section - View Mode
```jsx
<div className="glass-panel p-6 mb-6">
  <h2>Account Settings</h2>
  
  {/* User ID */}
  [User ID field - read only with copy button]
  
  {/* Email */}
  [Email field - read only]
  
  {/* Display Name - View Mode */}
  <div className="flex items-center justify-between p-3">
    <input disabled value="John Doe" />
    <button>Edit</button>
  </div>
</div>
```

### Account Section - Edit Mode
```jsx
<div className="glass-panel p-6 mb-6">
  <h2>Account Settings</h2>
  
  {/* Display Name - Edit Mode */}
  <div className="flex gap-2">
    <input 
      autoFocus
      value={displayName}
      onChange={(e) => setDisplayName(e.target.value)}
      placeholder="Enter your display name"
    />
    <button>Cancel</button>
    <button className="bg-blue-600">Save</button>
  </div>
  
  {/* Success Message */}
  <p className="text-green-400">✓ Name saved successfully</p>
</div>
```

### Theme Selector
```jsx
<div className="glass-panel p-6 mb-6">
  <h2>Appearance</h2>
  
  <div className="grid grid-cols-3 gap-3">
    {/* Light Theme */}
    <button 
      onClick={() => setTheme('light')}
      className={theme === 'light' ? 'border-yellow-400' : 'border-white/10'}
    >
      <Sun size={24} />
      Light
    </button>
    
    {/* Dark Theme */}
    <button 
      onClick={() => setTheme('dark')}
      className={theme === 'dark' ? 'border-blue-400' : 'border-white/10'}
    >
      <Moon size={24} />
      Dark
    </button>
    
    {/* System Theme */}
    <button 
      onClick={() => setTheme('system')}
      className={theme === 'system' ? 'border-green-400' : 'border-white/10'}
    >
      <Monitor size={24} />
      System
    </button>
  </div>
</div>
```

### Social Networks Grid
```jsx
<div className="glass-panel p-6">
  <h2>Connected Networks</h2>
  
  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
    {networks.map(network => (
      <div 
        key={network.id}
        onClick={() => toggleNetwork(network.id)}
        className={isConnected ? 'border-green-500' : 'border-white/10'}
      >
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <NetworkIcon />
            <div>
              <p>{network.name}</p>
              <p className="text-xs text-zinc-500">{network.description}</p>
            </div>
          </div>
          {isConnected && (
            <div className="bg-green-500/20 px-2 py-1">
              ✓ Connected
            </div>
          )}
        </div>
      </div>
    ))}
  </div>
</div>
```

### Service Status Widget
```jsx
<div className="p-4 bg-green-500/10 border-green-500/20">
  <div className="flex items-center gap-2 mb-3">
    <CheckCircle className="text-green-400" />
    <p>All services configured</p>
  </div>
  
  <div className="space-y-2">
    {services.map(([name, status]) => (
      <div key={name} className="flex justify-between">
        <span>{name}</span>
        <div className="flex items-center gap-1">
          <DotIndicator available={status.available} />
          <span>{status.available ? 'Ready' : 'Not configured'}</span>
        </div>
      </div>
    ))}
  </div>
</div>
```

## Color Scheme

### Dark Theme (Default)
```css
--color-background: #09090b  /* zinc-950 */
--color-surface: #18181b     /* zinc-900 */
Text: white
Accents: blue, purple, green
```

### Light Theme
```css
--color-background: #f5f5f5  /* light gray */
--color-surface: #ffffff     /* white */
Text: slate-900
Accents: blue, purple, green
Borders: slate-200
```

## Interaction Flow

### Edit Display Name
1. User clicks "Edit" button
2. Input becomes focused and editable
3. User types new name
4. User clicks "Save" or "Cancel"
5. If saved:
   - Show ✓ success message
   - Return to view mode
   - Name persists in localStorage

### Switch Theme
1. User clicks Light/Dark/System button
2. Theme class applied to document root
3. CSS variables updated
4. All colors transition smoothly (300ms)
5. Preference saved to localStorage
6. Theme persists across sessions

### Connect Network
1. User clicks network card
2. Card highlights with green border
3. "Connected ✓" badge appears
4. Connection saved to localStorage
5. User can click again to disconnect

### Check Service Status
1. Component mounts
2. Fetches `/api/services/status` quietly
3. Displays status of each service
4. Auto-refreshes every 5 minutes
5. Gracefully handles network errors

## Responsive Behavior

### Mobile (< 768px)
- Settings content takes full width
- Network cards stack vertically (1 column)
- Theme buttons remain 3 columns
- All input fields expand to full width
- Padding reduced for smaller screens

### Tablet (768px - 1024px)
- Network cards: 2 columns
- Settings max-width: 3xl
- Normal spacing

### Desktop (> 1024px)
- Network cards: 2 columns
- Settings max-width: 3xl
- Full spacing and hover effects

## Accessibility Features

✅ **Keyboard Navigation**
- Tab through all interactive elements
- Enter/Space to activate buttons
- Shift+Tab to go backward

✅ **Focus Indicators**
- Clear focus ring on inputs and buttons
- Visible focus states for theme selector

✅ **Color Contrast**
- All text meets WCAG AA standards
- Status indicators have text labels, not just color

✅ **Screen Readers**
- Semantic HTML structure
- ARIA labels on icon-only buttons
- Form labels properly associated

## Theme Example Transform

### When User Selects "Light"
```
1. localStorage.setItem('openshorts-theme', 'light')
2. document.documentElement.classList.add('light')
3. document.documentElement.classList.remove('dark')
4. CSS variables re-evaluated:
   --color-background: #f5f5f5
   --color-surface: #ffffff
5. All components re-render with light colors
6. text-white → text-slate-900
7. bg-background → bg-#f5f5f5
```

## Test Cases

- [ ] Account info displays correctly on load
- [ ] User ID copy button works
- [ ] Display name edit mode activates
- [ ] Display name saves and persists
- [ ] Cancel discards changes
- [ ] Light theme applies correctly
- [ ] Dark theme applies correctly
- [ ] System theme respects OS preference
- [ ] Theme persists on page reload
- [ ] Network toggle saves state
- [ ] Network state persists on reload
- [ ] Service status loads without error
- [ ] Service status shows correct data
- [ ] All components work in light/dark modes
- [ ] Mobile layout is responsive
- [ ] Keyboard navigation works
- [ ] No console errors

