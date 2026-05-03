package in.sfscollege.blixtro;

import android.os.Bundle;
import androidx.core.splashscreen.SplashScreen;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        // Install the Android 12+ SplashScreen API before super.onCreate()
        // so the launch theme transitions correctly to the app theme.
        SplashScreen.installSplashScreen(this);
        super.onCreate(savedInstanceState);
    }
}
