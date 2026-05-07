import { useEffect, useState } from 'react'
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
} from 'react-router-dom'
import { AuthenticatedLayout } from './components/layout/AuthenticatedLayout'
import { AuthProvider } from './features/auth/AuthContext'
import { AuthLayout } from './features/auth/pages/AuthLayout'
import { ForgotPasswordPage } from './features/auth/pages/ForgotPasswordPage'
import { LoginPage } from './features/auth/pages/LoginPage'
import { ProfileMissingPage } from './features/auth/pages/ProfileMissingPage'
import { AdminPage } from './pages/AdminPage'
import { NutritionistDashboardPage } from './pages/nutritionist/NutritionistDashboardPage'
import { NutritionistChatPage } from './pages/nutritionist/NutritionistChatPage'
import { PatientDetailPage } from './pages/nutritionist/PatientDetailPage'
import { PatientsPage } from './pages/nutritionist/PatientsPage'
import { PatientWorkspacePage } from './pages/patient/PatientWorkspacePage'
import {
  ProtectedRoute,
  PublicOnlyRoute,
  RoleRedirect,
} from './routes/routeGuards'

function App() {
  const [isDark, setIsDark] = useState(() => {
    return localStorage.getItem('star-nutri-theme') === 'dark'
  })

  useEffect(() => {
    document.documentElement.classList.toggle('dark', isDark)
    localStorage.setItem('star-nutri-theme', isDark ? 'dark' : 'light')
  }, [isDark])

  function toggleTheme() {
    setIsDark((current) => !current)
  }

  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route
            element={
              <PublicOnlyRoute>
                <AuthLayout isDark={isDark} onToggleTheme={toggleTheme}>
                  <LoginPage />
                </AuthLayout>
              </PublicOnlyRoute>
            }
            path="/login"
          />
          <Route
            element={
              <PublicOnlyRoute>
                <AuthLayout isDark={isDark} onToggleTheme={toggleTheme}>
                  <ForgotPasswordPage />
                </AuthLayout>
              </PublicOnlyRoute>
            }
            path="/forgot-password"
          />

          <Route element={<ProfileMissingPage />} path="/auth/profile-missing" />

          <Route element={<ProtectedRoute allowedRoles={['admin']} />}>
            <Route
              element={
                <AuthenticatedLayout isDark={isDark} onToggleTheme={toggleTheme} />
              }
            >
              <Route element={<AdminPage />} path="/admin" />
              <Route element={<AdminPage />} path="/admin/users" />
            </Route>
          </Route>

          <Route element={<ProtectedRoute allowedRoles={['nutritionist']} />}>
            <Route
              element={
                <AuthenticatedLayout isDark={isDark} onToggleTheme={toggleTheme} />
              }
            >
              <Route element={<NutritionistDashboardPage />} path="/nutritionist" />
              <Route element={<PatientsPage />} path="/nutritionist/patients" />
              <Route element={<PatientsPage mode="create" />} path="/nutritionist/patients/new" />
              <Route element={<PatientDetailPage />} path="/nutritionist/patients/:patientId" />
              <Route element={<NutritionistChatPage />} path="/nutritionist/chat" />
            </Route>
          </Route>

          <Route element={<ProtectedRoute allowedRoles={['patient']} />}>
            <Route
              element={
                <AuthenticatedLayout isDark={isDark} onToggleTheme={toggleTheme} />
              }
            >
              <Route element={<PatientWorkspacePage />} path="/patient" />
              <Route element={<PatientWorkspacePage view="diet" />} path="/patient/diet" />
              <Route element={<PatientWorkspacePage view="workout" />} path="/patient/workout" />
              <Route element={<PatientWorkspacePage view="metrics" />} path="/patient/metrics" />
              <Route element={<PatientWorkspacePage view="evolution" />} path="/patient/evolution" />
              <Route element={<PatientWorkspacePage view="chat" />} path="/patient/chat" />
              <Route element={<PatientWorkspacePage view="profile" />} path="/patient/profile" />
            </Route>
          </Route>

          <Route element={<RoleRedirect />} path="/" />
          <Route element={<Navigate replace to="/" />} path="*" />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
