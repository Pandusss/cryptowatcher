import { Route, Routes as RouterRoutes } from 'react-router-dom'

import { MainPage } from '@pages'
import { CreateNotificationPage } from '@pages'
import { ChooseCoinPage } from '@pages'
import { CoinDetailsPage } from '@pages'
import { DndSettingsPage } from '@pages'

import { ROUTES_NAME } from './constants/routes'

const Routes = () => {
  return (
    <RouterRoutes>
      <Route path={ROUTES_NAME.MAIN} element={<MainPage />} />
      <Route
        path={ROUTES_NAME.CREATE_NOTIFICATION}
        element={<CreateNotificationPage />}
      />
      <Route path={ROUTES_NAME.CHOOSE_COIN} element={<ChooseCoinPage />} />
      <Route path={ROUTES_NAME.COIN_DETAILS} element={<CoinDetailsPage />} />
      <Route
        path={ROUTES_NAME.EDIT_NOTIFICATION}
        element={<CreateNotificationPage />}
      />
      <Route path={ROUTES_NAME.DND_SETTINGS} element={<DndSettingsPage />} />
    </RouterRoutes>
  )
}

export default Routes

