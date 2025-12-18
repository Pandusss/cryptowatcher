interface BaseConfig {
  isDev?: boolean
  isProd?: boolean
  apiHost: string
  accessToken?: string
  botName: string
  appName: string
}

class Config implements BaseConfig {
  isDev?: boolean | undefined
  isProd?: boolean | undefined
  apiHost: string
  accessToken?: string | undefined
  botName: string
  appName: string

  constructor(config: BaseConfig) {
    this.isDev = config.isDev
    this.isProd = config.isProd
    this.apiHost = config.apiHost
    this.accessToken = config.accessToken
    this.botName = config.botName
    this.appName = config.appName
  }

  get botLink(): string {
    return `https://t.me/${this.botName}`
  }

  get miniAppLink(): string {
    return `https://t.me/${this.botName}/${this.appName}`
  }
}

const devConfigBase: BaseConfig = {
  isDev: true,
  apiHost: import.meta.env.VITE_API_HOST || 'http://localhost:8000',
  botName: 'cryptowatcher_bot',
  appName: 'app',
  accessToken: import.meta.env.VITE_ACCESS_TOKEN,
}

const prodConfigBase: BaseConfig = {
  isProd: true,
  apiHost: import.meta.env.VITE_API_BASE_URL || 'https://watcher.negarant.org/api',
  botName: 'cryptowatcher_bot',
  appName: 'app',
}

let config

switch (import.meta.env.MODE) {
  case 'production':
    config = new Config(prodConfigBase)
    break
  default:
    config = new Config(devConfigBase)
}

export default config as Config


